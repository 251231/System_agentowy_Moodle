"""
Test Strategy A on actual page.xml format shown by the user.
Expected: {mlang pl} block gets Polish translation, {mlang en} stays English.
"""
import re, sys
sys.path.insert(0, '.')
from moodle_processor import MoodleMBZProcessor

# Simulate the actual page.xml format from the user's example
sample_xml = (
    '<activity id="3877" moduleid="36358" modulename="page">\n'
    '<page id="3877">\n'
    '<name>{mlang pl}Gemini{mlang}{mlang en}Gemini{mlang}</name>\n'
    '<content>{mlang pl}<p>Gemini is an LLM by Google.</p>{mlang}'
    '{mlang en}<p>Gemini is an LLM by Google.</p>{mlang}</content>\n'
    '</page>\n'
    '</activity>'
)

print("=== INPUT ===")
print(sample_xml[:300])

# Mock processor (no API, simulates translation)
proc = MoodleMBZProcessor(source_lang='en', target_langs=['en', 'pl'], api_type='none')
result, changes = proc._replace_in_tag(sample_xml, 'name')
result, changes2 = proc._replace_in_tag(result, 'content')

print(f"\n=== OUTPUT (name changes={changes}, content changes={changes2}) ===")
print(result[:500])

# Verify: {mlang pl} should have [pl] prefix now
assert '{mlang pl}[pl] Gemini{mlang}' in result, "name translation FAILED"
assert '{mlang pl}[pl] <p>Gemini is an LLM' in result, "content translation FAILED"
assert '{mlang en}Gemini{mlang}' in result, "english name should be unchanged"
print("\n✓ All assertions passed!")
