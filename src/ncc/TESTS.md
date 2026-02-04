
uv run ncc
- should get top level help

uv run ncc backup
- should get backup specific help

uv run ncc backup --devices src/ncc/backup/test.json
- backup runs with provided targets file and uses default backup directory
- should be one failure for device without credentials

uv run ncc --debug backup --devices src/ncc/backup/test.json
- backup runs with provided targets file and uses default backup directory
- debugging output rather than rich console

uv run ncc backup --devices src/ncc/backup/test.json --silent 
- backup runs with provided targets file and uses default backup directory
- silent output

uv run ncc --username lab --password lab123 backup --devices src/ncc/backup/test.json --directory backups --tag test
- backup runs with provided targets file and uses specified backup directory
- provides username and password on command line
- sets tag of test
