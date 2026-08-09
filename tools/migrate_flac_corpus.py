import shutil
from pathlib import Path

def migrate():
    repo_root = Path(__file__).parent.parent
    old_dir = repo_root / "userdata" / "flac"
    new_dir = repo_root / "userdata" / "voice_recordings_PRIVATE"
    
    if not old_dir.exists():
        print("No 'flac' directory found. Nothing to migrate.")
        return
        
    for file_path in old_dir.glob("*.flac"):
        if file_path.stat().st_size == 0:
            print(f"Deleting 0-byte file: {file_path.name}")
            file_path.unlink()
            continue
            
        # File name is like: 2026-08-04_17-38-33-832928.flac
        try:
            year, month, day = file_path.name.split("_")[0].split("-")
        except ValueError:
            print(f"Skipping unrecognised name: {file_path.name}")
            continue

        target_dir = new_dir / year / month / day
        target_dir.mkdir(parents=True, exist_ok=True)

        shutil.move(str(file_path), str(target_dir / file_path.name))

    # Try to remove old_dir if it's empty
    try:
        old_dir.rmdir()
        print("Migrated successfully. Old 'flac' directory removed.")
    except OSError:
        print("Migrated files, but 'flac' directory was not empty. Left it intact.")

if __name__ == "__main__":
    migrate()
