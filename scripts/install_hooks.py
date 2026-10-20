"""Install the leak-gate pre-commit hook into .git/hooks/."""
import shutil
import stat
from pathlib import Path

root = Path(__file__).resolve().parent.parent
dest = root / ".git" / "hooks" / "pre-commit"
shutil.copyfile(root / "scripts" / "pre-commit", dest)
dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
print(f"installed {dest}")
