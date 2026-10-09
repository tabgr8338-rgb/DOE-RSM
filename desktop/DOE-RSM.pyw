"""DOE-RSM デスクトップ版の起動ファイル（インストーラーが作るショートカットから pythonw で実行する）。"""
import sys

from doe_rsm.desktop import main

sys.exit(main())
