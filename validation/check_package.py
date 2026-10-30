"""Validate skill metadata and portable repository references."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'mv-script'


def main():
    content = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    parts = content.split('---', 2)
    assert len(parts) == 3 and not parts[0].strip(), 'missing frontmatter'
    meta = yaml.safe_load(parts[1])
    assert meta['name'] == 'mv-script'
    assert isinstance(meta['description'], str) and 0 < len(meta['description']) < 1024
    ui = yaml.safe_load((SKILL / 'agents/openai.yaml').read_text(encoding='utf-8'))
    assert '$mv-script' in ui['interface']['default_prompt']
    assert 25 <= len(ui['interface']['short_description']) <= 64
    documents = list(SKILL.rglob('*.md')) + [ROOT / name for name in
        ['README.md', 'README.en.md', 'INSTALL.md', 'CONTRIBUTING.md', 'docs/validation.md']]
    checked = 0
    for document in documents:
        text = document.read_text(encoding='utf-8')
        assert not re.search(r'/Users/|/home/[^\s/]+/', text), document
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            if re.match(r'https?://|mailto:|#', target):
                continue
            resolved = document.parent / target.split('#')[0]
            assert resolved.exists(), (document, target)
            checked += 1
    print('Skill metadata and %s local references are valid.' % checked)


if __name__ == '__main__':
    main()
