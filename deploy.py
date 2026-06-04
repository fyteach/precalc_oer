import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader


DISPLAY_DATE_FORMAT = "%B {day}, %Y"
VISIBLE_DATE_PATTERNS = [
    r"(?i)last\s+updated\s*:\s*(\d{4}-\d{2}-\d{2})",
    r"(?i)last\s+updated\s*:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    r"(?i)last\s+updated\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
]
VISIBLE_DATE_FORMATS = ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y"]


def format_display_date(date_value: datetime) -> str:
    return date_value.strftime(DISPLAY_DATE_FORMAT.format(day=date_value.day))


def find_front_page_pdf(md_file: Path) -> Path | None:
    md_text = md_file.read_text(encoding='utf-8')
    matches = re.findall(r"\(([^)]+\.pdf)\)", md_text, flags=re.IGNORECASE)
    for match in matches:
        pdf_name = Path(match).name
        for candidate in (Path(pdf_name), Path('deploy') / pdf_name):
            if candidate.exists():
                return candidate

    pdf_files = sorted(Path('.').glob('*.pdf'))
    return pdf_files[0] if pdf_files else None


def parse_visible_pdf_date(page_text: str) -> datetime | None:
    for pattern in VISIBLE_DATE_PATTERNS:
        match = re.search(pattern, page_text)
        if not match:
            continue

        date_text = match.group(1).strip()
        for date_format in VISIBLE_DATE_FORMATS:
            try:
                return datetime.strptime(date_text, date_format)
            except ValueError:
                continue

    return None


def parse_pdf_metadata_date(metadata_date: str | None) -> datetime | None:
    if not metadata_date:
        return None

    match = re.search(r"(?:D:)?(\d{4})(\d{2})(\d{2})", metadata_date)
    if not match:
        return None

    year, month, day = (int(value) for value in match.groups())
    return datetime(year, month, day)


def resolve_compile_date(md_file: Path) -> tuple[datetime, str]:
    pdf_path = find_front_page_pdf(md_file)
    if pdf_path:
        reader = PdfReader(str(pdf_path))
        if reader.pages:
            visible_date = parse_visible_pdf_date(reader.pages[0].extract_text() or '')
            if visible_date:
                return visible_date, f"front page of {pdf_path.name}"

        metadata = reader.metadata or {}
        metadata_date = parse_pdf_metadata_date(metadata.get('/ModDate') or metadata.get('/CreationDate'))
        if metadata_date:
            return metadata_date, f"metadata of {pdf_path.name}"

    return datetime.now(), "current compilation time"

def main():
    # Change to script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    print(f"Working in: {script_dir}")
    
    # Find the first markdown file
    md_files = list(Path('.').glob('*.md'))
    if not md_files:
        print("❌ No .md files found!")
        return
    
    md_file = md_files[0]
    print(f"Using markdown file: {md_file.name}")

    compile_date, compile_date_source = resolve_compile_date(md_file)
    compile_date_text = format_display_date(compile_date)
    print(f"Using compile date from {compile_date_source}: {compile_date_text}")
    
    # Find CSS file (optional)
    css_files = list(Path('.').glob('*.css'))
    css_file = css_files[0] if css_files else None
    if css_file:
        print(f"Using CSS file: {css_file.name}")
    
    # Create deploy folder
    deploy_dir = Path('deploy')
    deploy_dir.mkdir(exist_ok=True)
    
    # Convert to HTML
    output_html = 'index.html'
    cmd = ['pandoc', '-s', md_file.name, '-o', output_html]
    if css_file:
        cmd.extend(['--css', css_file.name])
    
    subprocess.run(cmd, check=True)
    print(f"✓ Created {output_html}")

    html_path = Path(output_html)
    if html_path.exists():
        html_text = html_path.read_text(encoding='utf-8')
        html_text = html_text.replace('{{COMPILE_DATE}}', compile_date_text)
        html_path.write_text(html_text, encoding='utf-8')
        print(f"✓ Stamped compile date: {compile_date_text}")
    
    # Copy CSS file (if exists) - overwrite if exists
    if css_file and css_file.name:
        css_path = Path(css_file.name)
        if css_path.exists():
            # Using os.replace() for atomic overwrite (Python 3.3+)
            shutil.copy2(css_path, deploy_dir / css_path.name)
            print(f"✓ Copied CSS: {css_path}")

    # Move HTML file - overwrite if exists
    if html_path.exists():
        # Using os.replace() for atomic move with overwrite
        dest = deploy_dir / html_path.name
        if dest.exists():
            dest.unlink()  # Remove existing file
        shutil.move(html_path, deploy_dir)
        print(f"✓ Moved {output_html}")

    # Move PDF files - overwrite if exists
    for pdf_file in Path('.').glob('*.pdf'):
        if pdf_file.exists():
            dest = deploy_dir / pdf_file.name
            if dest.exists():
                dest.unlink()  # Remove existing file
            shutil.move(pdf_file, deploy_dir)
            print(f"✓ Moved {pdf_file}")
      
    print(f"\n✅ Done! Files deployed to: {deploy_dir.absolute()}")

if __name__ == "__main__":
    main()