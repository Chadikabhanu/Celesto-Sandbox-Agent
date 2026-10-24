import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reporting.generator import generate_all_reports


async def main():
    print("Generating Phase 4 reports...")
    reports = await generate_all_reports()
    for name, path in reports.items():
        print(f"  [OK] Generated {name}: {path}")
    print("All Phase 4 reports generated successfully.")


if __name__ == "__main__":
    asyncio.run(main())
