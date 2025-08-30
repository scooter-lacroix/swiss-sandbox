#!/bin/bash
cd /home/stan
# Generate a clear file listing
find swiss-sandbox -type f | sort > swiss-sandbox/file_listing.txt
# Create zip export with listing included
zip -r swiss-sandbox-export.zip swiss-sandbox
echo "Workspace exported to /home/stan/swiss-sandbox-export.zip (includes file_listing.txt for easy access)"