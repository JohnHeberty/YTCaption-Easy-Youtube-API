#!/usr/bin/env python3
"""
Script para corrigir TODAS as exceções que passam details= explicitamente.
Remove details= de super().__init__() quando há **kwargs.
"""
import re

# Read the file
with open('/root/YTCaption-Easy-Youtube-API/services/make-video/app/shared/exceptions_v2.py', 'r') as f:
    content = f.read()

# Find all exception classes that have details= in super().__init__()
# Pattern: class with __init__ that has **kwargs and details= in super()
pattern = r'(class \w+Exception\([^)]+\):.*?def __init__\([^)]*\*\*kwargs\):[^}]*?)(super\(\).__init__\([^)]*details=\{[^}]+\}[^)]*\*\*kwargs\))'

def fix_exception(match):
    """Fix a single exception class"""
    before = match.group(1)
    super_call = match.group(2)
    
    # Extract details dict from super call
    details_match = re.search(r'details=(\{[^}]+\})', super_call)
    if not details_match:
        return match.group(0)
    
    details_dict = details_match.group(1)
    
    # Remove details= from super call
    fixed_super = re.sub(r',?\s*details=\{[^}]+\}', '', super_call)
    
    # Add details extraction before super call
    indent = '        '
    details_fix = f'''{indent}# Extract and merge details to prevent conflicts
{indent}merged_details = kwargs.pop('details', {{}})
{indent}# Add this exception's specific details
{indent}exception_details = {details_dict}
{indent}merged_details.update(exception_details)
{indent}'''
    
    # Replace details= with merged_details
    fixed_super = fixed_super.replace('**kwargs)', 'details=merged_details, **kwargs)')
    
    return before + details_fix + fixed_super

# This is complex, let's do it manually for now
print("Pattern too complex for regex. Need manual fixes.")
print(f"Found {content.count('details={')} instances of details= in file")

