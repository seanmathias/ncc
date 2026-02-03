"""
Backup CLI commands.

Provides commands for performing device configuration backups.
"""

#from doctest import debug
from doctest import debug
import os
import sys
import json
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from napalm import get_network_driver

from ncc.core.config import config
from ncc.core.logging import logger
from ncc.cli.main import pass_context, NCCContext

console = Console()


@click.option(
    "--vendors",
    is_flag=True,
    help="List supported vendors"
)
@click.option(
    "--silent",
    is_flag=True,
    help="No console output"
)
@click.option(
    "--devices",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON file of target devices to archive configuraion backups"
)
@click.option(
    "--directory",
    type=click.Path(exists=False, file_okay=False, resolve_path=True, path_type=Path),
    help="Path to archive configuration backups"
)


@click.command(name="backup", help="Perform device configuration backups.")
@pass_context
def backup(
    ctx: NCCContext,
    vendors: Optional[bool],
    silent: Optional[bool],
    devices: Path,
    directory: Optional[Path]
):

    debug = ctx.debug
    workers = ctx.workers
    username = ctx.username
    password = ctx.password

    try:
        # vendor list requested
        if vendors:
            list_supported_vendors()
            sys.exit(0)

        # credentials from command line
        credentials = {}
        if username and not password or password and not username:
            console.print("[bold red]Error:[/bold red] Both username and password must be provided.")
            sys.exit(1)
        if username and password:
            credentials['username'] = username
            credentials['password'] = password
            logger.debug("Using credentials from command line for devices missing them")

        # Set number of parallel workers
        if workers is None:
            workers = 5  # default number of parallel tasks
        logger.debug(f"Using {workers} parallel backup tasks")
        
        # Get the device inventory file
        if devices is None:
            console.print("[bold red]Error:[/bold red] Devices file is required.")
            console.print()
            click.echo(backup.get_help(click.Context(backup)))
            sys.exit(1)
        
        # Create backup directory
        if directory is None:
            directory = Path.cwd() / "ncc_backups"

        directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Configuration backup directory: {directory}")
        
        # Load inventory
        inventory = load_inventory(devices)
        logger.debug(f"Loaded {len(inventory)} devices from {devices}")

        # Apply credentials from the command line to devices missing them
        if credentials:
            for device in inventory:
                if 'username' not in device or not device['username']:
                    device['username'] = credentials['username']
                if 'password' not in device or not device['password']:
                    device['password'] = credentials['password']

        # Print device count by type
        device_types = {}
        for device in inventory:
            dt = device['device_type']
            device_types[dt] = device_types.get(dt, 0) + 1

        if debug:
            logger.debug("\nDevices to backup:")
            for dt, count in sorted(device_types.items()):
                vendor_name = config.supported_vendors.get(dt, dt)
                logger.debug(f"  - {vendor_name}: {count} device(s)")
        if not debug and not silent:
            table = Table(title="Devices to Backup", show_lines=True)
            table.add_column("Device Type", style="cyan", no_wrap=True)
            table.add_column("Count", style="magenta", justify="right")
            for dt, count in sorted(device_types.items()):
                vendor_name = config.supported_vendors.get(dt, dt)
                table.add_row(vendor_name, str(count))
            console.print(table)
            console.print()

        # Perform device configuration backups
        if debug:
            logger.debug("Starting backup process...")
        if not debug and not silent:
            console.print("[bold cyan]Starting backup process...[/bold cyan]")
        results = backup_all_devices(inventory, directory, workers, debug, silent)

        # Print summary
        if debug:
            logger.debug("Backup process complete")
        if not debug and not silent:
            print_summary(results)
            console.print("[bold green]Backup complete![/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.exception("Failed to backup configurations")
        sys.exit(1)


def load_inventory(inventory_file: Path) -> dict:
    """Load device inventory from JSON file"""
    try:
        with open(inventory_file, 'r') as f:
            inventory = json.load(f)
        logger.debug(f"Loaded {len(inventory)} devices from inventory")
        
        # Validate device types
        for device in inventory:
            device_type = device.get('device_type')
            if not device_type:
                raise ValueError(f"Device {device.get('hostname')} missing 'device_type'")
            if device_type not in config.supported_vendors:
                logger.warning(
                    f"Device type '{device_type}' for {device.get('hostname')} "
                    f"is not in the known supported list, but will attempt connection"
                )
        
        return inventory
    except FileNotFoundError:
        logger.error(f"Inventory file {inventory_file} not found")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in inventory file: {e}")
        raise


def backup_all_devices(
        inventory: list, 
        directory: Path, 
        workers: int, 
        debug: bool, 
        silent: bool) -> list:
    """
    Backup configurations from all devices in parallel
    
    Args:
        inventory (list): List of device information dictionaries
        directory (Path): Directory to store backup files
        workers (int): Number of parallel backup tasks
        
    Returns:
        list: List of backup results
    """
    results = []
    
    # Use ThreadPoolExecutor for parallel backups
    with Progress() as progress:
        if not debug and not silent:
            task = progress.add_task("[cyan]Backing up devices...", total=len(inventory))
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all backup tasks
            device_futures = {
                executor.submit(backup_device, device, directory): device['hostname']
                for device in inventory
            }
            
            # Collect results as they complete
            for future in as_completed(device_futures):
                hostname = device_futures[future]
                try:
                    # get result from future
                    result = future.result()
                    results.append(result)
                    logger.debug(f"[{hostname}] Backup task completed")

                    if not debug and not silent:
                        # update progress bar
                        progress.update(task, advance=1)

                except Exception as e:
                    logger.error(f"[{hostname}] Unexpected error: {e}")
                    results.append({
                        'hostname': hostname,
                        'success': False,
                        'error': str(e)
                    })
                    if not debug and not silent:
                        # update progress bar
                        progress.update(task, advance=1)

    return results


def backup_device(device: dict, directory: Path) -> dict:
    """
    Backup configuration for a single device
    
    Args:
        device (list): Dictionary of device information
        directory (Path): Base directory to store backup files
        
    Returns:
        list: List of backup results
    """
    hostname = device['hostname']
    device_type = device['device_type']
    vendor_name = config.supported_vendors.get(device_type, device_type)
    driver = get_network_driver(device_type)
    
    logger.debug(f"[{hostname}] Starting backup using {vendor_name} driver")
    
    result = {
        'hostname': hostname,
        'device_type': device_type,
        'success': False,
        'filename': None,
        'error': None
    }

    try:
        optional_args = device.get('optional_args', {})
        conn = driver(
            hostname=hostname,
            username=device.get('username'),
            password=device.get('password'),
            optional_args=optional_args
        )
        conn.open()
        
        # get facts and update result
        facts = conn.get_facts()
        result['vendor'] = facts.get('vendor', 'unknown')
        result['model'] = facts.get('model', 'unknown')
        result['os_version'] = facts.get('os_version', 'unknown')
        result['hostname'] = facts.get('hostname', hostname.split('.')[0])

        # get running configuration
        logger.debug(f"[{hostname}] Retrieving running configuration")
        config_data = conn.get_config()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # file and directory setup
        backup_dir = Path(directory) / result['hostname']
        backup_dir.mkdir(parents=True, exist_ok=True)

        filename = Path(backup_dir) / f"{result['hostname']}_{timestamp}.cfg"
        
        # write configuration to file
        with open(filename, 'w') as f:
            f.write(config_data['running'])
        
        size = os.path.getsize(filename)
        logger.debug(f"[{hostname}] Backup successful: {filename} ({size} bytes)")
        
        result.update({
            'filename': str(filename),
            'size': size,
            'success': True
        })
        
    except Exception as e:
        logger.error(f"[{hostname}] Backup failed: {e}")
        result.update({
            'error': str(e)
        })
    finally:
        try:
            conn.close()
        except:
            pass

    return result


def print_summary(results):
    """Print detailed summary of backup operations"""
    total = len(results)
    successful = sum(1 for r in results if r['success'])
    failed = total - successful
    
    # Group by vendor
    vendor_stats = {}
    for result in results:
        if result['success']:
            vendor = result.get('vendor', 'unknown')
            if vendor not in vendor_stats:
                vendor_stats[vendor] = 0
            vendor_stats[vendor] += 1
    
    table = Table(title="Backup Summary", show_header=False, show_lines=True)
    #table.add_column("Metric", style="cyan", no_wrap=True)
    #table.add_column("Value", style="magenta", justify="right")
    table.add_row("Total Devices", str(total))
    table.add_row("Successful Backups", str(successful))
    table.add_row("Failed Backups", str(failed))
    console.print(table)
    console.print()
    
    if vendor_stats:
        table = Table(title="Backups by Vendor", show_lines=True)
        table.add_column("Vendor", style="cyan", no_wrap=True)
        table.add_column("Successful Backups", style="magenta", justify="right")
        for vendor, count in sorted(vendor_stats.items()):
            table.add_row(vendor, str(count))
        console.print(table)
        console.print()
    
    if failed > 0:
        table = Table(title="Failed Backups", show_lines=True)
        table.add_column("Hostname", style="cyan", no_wrap=True)
        table.add_column("Device Type", style="magenta", no_wrap=True)
        table.add_column("Error", style="red")
        for result in results:
            if not result['success']:
                table.add_row(
                    result['hostname'],
                    result['device_type'],
                    result['error']
                )
        console.print(table)
        console.print()
    
    if successful > 0:
        table = Table(title="Successful Backups", show_lines=True)
        table.add_column("Hostname", style="cyan", no_wrap=True)
        table.add_column("Device Type", style="magenta", no_wrap=True)
        table.add_column("Filename", style="green")
        table.add_column("Size (bytes)", style="yellow", justify="right")
        for result in results:
            if result['success']:
                table.add_row(
                    result['hostname'],
                    result['device_type'],
                    result['filename'],
                    f"{result['size']:,}"
                )
        console.print(table)
        console.print()


def list_supported_vendors():
    """Print list of supported vendors"""
    console.print("[bold cyan]Supported Vendor Device Types:[/bold cyan]")
    console.print("-" * 50)
    for device_type, description in sorted(config.supported_vendors.items()):
        console.print(f"  {device_type:20s} - {description}")
    console.print("-" * 50)
    console.print("\nNote: NAPALM supports additional community drivers.")
    console.print("See: https://napalm.readthedocs.io/\n")