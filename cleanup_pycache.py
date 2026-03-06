"""
Script to remove all __pycache__ directories from the project
"""
import os
import shutil
from pathlib import Path

def remove_pycache_dirs(root_dir="."):
    """Remove all __pycache__ directories recursively"""
    removed_count = 0
    removed_dirs = []
    
    # Walk through all directories
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip venv directory
        if 'venv' in dirpath or 'env' in dirpath:
            continue
            
        # Check if __pycache__ is in current directory
        if '__pycache__' in dirnames:
            pycache_path = os.path.join(dirpath, '__pycache__')
            try:
                shutil.rmtree(pycache_path)
                removed_dirs.append(pycache_path)
                removed_count += 1
                print(f"✅ Removed: {pycache_path}")
            except Exception as e:
                print(f"❌ Failed to remove {pycache_path}: {str(e)}")
    
    return removed_count, removed_dirs


if __name__ == "__main__":
    print("=" * 60)
    print("Cleaning up __pycache__ directories")
    print("=" * 60)
    print()
    
    count, dirs = remove_pycache_dirs()
    
    print()
    print("=" * 60)
    if count > 0:
        print(f"✅ Successfully removed {count} __pycache__ directories")
        print()
        print("Removed directories:")
        for d in dirs:
            print(f"  - {d}")
    else:
        print("✅ No __pycache__ directories found")
    print("=" * 60)
    print()
    print("Note: Python will automatically recreate these directories")
    print("when you run your application. They are already in .gitignore")
