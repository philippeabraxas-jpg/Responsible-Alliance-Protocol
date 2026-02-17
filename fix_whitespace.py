import sys

# Fix leading whitespace in files
files_to_fix = [
    'tbp-v4-hard-shield/audit_tools/verify_logs.py',
    'tbp-v4-hard-shield/core/audit_verifier.py'
]

for filepath in files_to_fix:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove leading whitespace from the entire file
        content = content.lstrip()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Fixed {filepath}")
    except Exception as e:
        print(f"❌ Error fixing {filepath}: {e}")
        sys.exit(1)

print("\n✅ All files fixed!")
