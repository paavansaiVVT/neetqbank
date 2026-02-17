#!/bin/bash
# Self-fix CRLF first (this file may arrive with \r from Windows/git)
sed -i 's/\r$//' "$0" 2>/dev/null || true

echo "Fixing CRLF line endings on deploy scripts..."
sed -i 's/\r$//' deploy_scripts/application-start.sh
sed -i 's/\r$//' deploy_scripts/fix-line-endings.sh
chmod +x deploy_scripts/application-start.sh
chmod +x deploy_scripts/fix-line-endings.sh
echo "Line-ending fix completed."
