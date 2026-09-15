#!/bin/zsh
cd "$(dirname "$0")/.."
export CHROMA_PATH="$PWD/.chroma"
python3 seed_chroma.py
status=$?
if [ $status -eq 0 ]; then
  echo ""
  echo "Done. Start or restart the Text-to-SQL Lab to use this local index."
fi
echo ""
read "?Press Return to close..."
exit $status
