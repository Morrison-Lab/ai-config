#!/usr/bin/env python3
import sys
import re
from pathlib import Path

def main():
    files_to_check = list(Path('hooks').rglob('test-*.py')) + list(Path('scripts').rglob('test_*.py'))
    
    failures = 0
    call_sites_examined = 0
    
    git_cmd_re = re.compile(r'(?:git|_git)[\s"\'`,()[\]a-zA-Z0-9_]*\b(?:init|clone)\b')
    branch_flag_re = re.compile(r'-b\b|--initial-branch\b|--branch\b|init\.defaultBranch')
    
    for file_path in files_to_check:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        in_docstring = False
        docstring_quote = ""
        
        for i, line in enumerate(lines):
            line_str = line.strip()
            
            # Simple docstring tracking
            if not in_docstring:
                if line_str.startswith('"""') or line_str.startswith("'''"):
                    if line_str.count('"""') == 1 or line_str.count("'''") == 1:
                        in_docstring = True
                        docstring_quote = '"""' if '"""' in line_str else "'''"
                        continue
            else:
                if docstring_quote in line_str:
                    in_docstring = False
                continue
            
            if line_str.startswith('#'):
                continue
                
            if git_cmd_re.search(line_str):
                if '# unpinned ok' in line_str:
                    call_sites_examined += 1
                    continue
                
                if branch_flag_re.search(line_str):
                    call_sites_examined += 1
                    continue
                
                print(f"{file_path}:{i+1}: Unpinned git fixture command: {line_str}")
                failures += 1
                call_sites_examined += 1

    print(f"Examined {call_sites_examined} git init/clone call sites.")
    if call_sites_examined == 0:
        print("ERROR: No call sites examined. Negative-control failure.")
        sys.exit(1)
        
    if failures > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
