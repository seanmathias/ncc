"""
Backup CLI commands.

Provides commands for performing device configuration backups.
"""


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
    "--tag",
    is_flag=False,
    help="Add tag to backup filename. No spaces allowed."
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
    tag: Optional[str],
    devices: Path,
    directory: Optional[Path]
):
    """Backup device configurations command."""
    try:
        # vendor list requested
        if vendors:
            list_supported_vendors()
            sys.exit(0)

        ctx.silent = silent
        ctx.tag = tag
        ctx.devices = devices
        ctx.directory = directory

        # Set number of parallel workers
        logger.debug(f"Using {ctx.workers} parallel backup tasks")
        
        # Tag for backup filenames
        if ctx.tag:
            if ' ' in ctx.tag:
                console.print("[bold red]Error:[/bold red] Tag cannot contain spaces.")
                raise ValueError("Tag cannot contain spaces")
            logger.debug(f"Using tag '{ctx.tag}' for backup filenames")

        # Get the device inventory file
        if ctx.devices is None:
            console.print("[bold red]Error:[/bold red] Devices file is required.")
            console.print()
            click.echo(backup.get_help(click.Context(backup)))
            sys.exit(1)
        logger.debug(f"Using device inventory file: {ctx.devices}")

        # Create backup directory
        if ctx.directory is None:
            ctx.directory = Path.cwd() / "ncc_backups"

        ctx.directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Configuration backup directory: {ctx.directory}")
        
        # Load inventory
        ctx.inventory = load_inventory(ctx)
        logger.debug(f"Loaded {len(ctx.inventory)} devices from {ctx.devices}")
        # Use credentials from command line where needed if provided
        if ctx.username and ctx.password:
            for device in ctx.inventory:
                if device.get('username') is None or device.get('password') is None:
                    logger.debug(f"[{device.get('hostname')}] Using CLI provided credentials")
                    device['username'] = ctx.username
                    device['password'] = ctx.password

        # Perform device configuration backups
        logger.debug("Starting backup job...")
        if not ctx.debug and not ctx.silent:
            console.print("[bold cyan]Starting backup job...[/bold cyan]")

        # Job Summary
        # workers, device count, devices file, directory, tag, credentials
        if not ctx.debug and not ctx.silent:
            console.print(
                f"Backing up [bold magenta]{len(ctx.inventory)}[/bold magenta] "
                f"devices using [bold magenta]{ctx.workers}[/bold magenta] parallel tasks"
            )
            console.print(f"Device inventory file: [bold magenta]{ctx.devices}[/bold magenta]")            
            console.print(f"Backup directory: [bold magenta]{ctx.directory}[/bold magenta]")
            if ctx.tag:
                console.print(f"Using tag: [bold magenta]{ctx.tag}[/bold magenta]")
            if ctx.username and ctx.password:
                console.print("Using provided username and password for devices missing credentials")
            console.print()

        results = backup_all_devices(ctx)

        # Print summary
        if ctx.debug:
            successful = sum(1 for r in results if r['success'])
            failed = len(results) - successful
            logger.debug(f"Backup Summary: {successful} successful, {failed} failed")
            logger.debug("Backup process complete")
        if not ctx.debug and not ctx.silent:
            print_summary(results)
            console.print("[bold green]Backup job complete![/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.exception("Failed to backup configurations")
        sys.exit(1)

def load_inventory(ctx: NCCContext) -> list:
    """Load device inventory from JSON file"""
    try:
        with open(ctx.devices, 'r') as f:
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
        logger.error(f"Inventory file {ctx.devices} not found")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in inventory file: {e}")
        raise


def backup_all_devices(ctx: NCCContext) -> list:
    """
    Backup configurations from all devices in parallel
    
    Args:
        inventory (list): List of device information dictionaries
        params (Params): Parameters object containing backup configuration
        
    Returns:
        list: List of backup results
    """
    results = []
    
    # Use ThreadPoolExecutor for parallel backups
    with Progress() as progress:
        if not ctx.debug and not ctx.silent:
            task = progress.add_task("[cyan]Backing up devices...", total=len(ctx.inventory))
        
        with ThreadPoolExecutor(max_workers=ctx.workers) as executor:
            # Submit all backup tasks
            device_futures = {
                executor.submit(backup_device, device, ctx): device['hostname']
                for device in ctx.inventory
            }
            
            # Collect results as they complete
            for future in as_completed(device_futures):
                hostname = device_futures[future]
                try:
                    # get result from future
                    result = future.result()
                    results.append(result)
                    logger.debug(f"[{hostname}] Backup task completed")

                    if not ctx.debug and not ctx.silent:
                        # update progress bar
                        progress.update(task, advance=1)

                except Exception as e:
                    logger.error(f"[{hostname}] Unexpected error: {e}")
                    results.append({
                        'hostname': hostname,
                        'success': False,
                        'error': str(e)
                    })
                    if not ctx.debug and not ctx.silent:
                        # update progress bar
                        progress.update(task, advance=1)

    return results


def backup_device(device: dict, ctx: NCCContext) -> dict:
    """
    Backup configuration for a single device
    
    Args:
        device (list): Dictionary of device information
        params (Params): Parameters object containing backup configuration
        
    Returns:
        dict: Backup result for the device
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
        backup_dir = Path(ctx.directory) / result['hostname']
        backup_dir.mkdir(parents=True, exist_ok=True)

        if ctx.tag:
            filename = Path(backup_dir) / f"{result['hostname']}_{ctx.tag}_{timestamp}.cfg"
        else:
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
        logger.debug(f"[{hostname}] Backup failed: {e}")
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
    console.print()
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