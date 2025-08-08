#!/usr/bin/env python3
"""
Run database migrations
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from migrations.migration_runner import migration_runner

# Import migrations
import importlib.util
import os

def load_migration(file_path):
    """Load migration from file"""
    spec = importlib.util.spec_from_file_location("migration", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migration_001


async def main():
    """Run all migrations"""
    print("Starting database migrations...")
    
    # Load and add all migrations
    migrations_dir = project_root / "migrations"
    migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.py') and f[0].isdigit()])
    
    for migration_file in migration_files:
        migration_path = migrations_dir / migration_file
        try:
            migration = load_migration(migration_path)
            migration_runner.add_migration(migration)
            print(f"Loaded migration: {migration_file}")
        except Exception as e:
            print(f"Failed to load migration {migration_file}: {e}")
    
    # Run migrations
    await migration_runner.run_migrations()
    
    print("Migrations completed!")


if __name__ == "__main__":
    asyncio.run(main())