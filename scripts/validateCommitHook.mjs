import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Setup paths
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sopPath = path.resolve(__dirname, '../config/gitops_agent_sop.json');
const commitMsgFile = process.argv[2];

if (!fs.existsSync(commitMsgFile)) process.exit(0);

// Load the SOP
const sop = JSON.parse(fs.readFileSync(sopPath, 'utf8'));
const matrix = sop.gitmoji_reference_matrix;

const safePath = path.resolve(process.cwd(), commitMsgFile);
if (!safePath.startsWith(process.cwd())) process.exit(1);

const rawMsg = fs.readFileSync(safePath, 'utf8');
const lines = rawMsg.split('\n').filter(line => !line.trim().startsWith('#'));
if (lines.length === 0) process.exit(0);

const errors = [];
const subjectLine = lines[0].trim();

// Regex to capture: Emoji (unicode or shortcode), CC Type, Scope (optional), Breaking (!), and Subject
const commitRegex = /^((?:\p{Emoji_Presentation}|\p{Extended_Pictographic})\uFE0F?|:[a-z0-9_+\-]+:)\s+([a-z]+)(?:\(([a-z0-9\-,\s]+)\))?(!?):\s+(.+)$/u;
const match = subjectLine.match(commitRegex);

let ccType = '';
if (!match) {
    errors.push(`Invalid Hybrid Syntax in subject line.\n   Expected: <emoji> <cc_type>(<scope>): <subject>\n   Received: ${subjectLine}`);
} else {
    const [ , emoji, parsedCcType, scope, breaking, subject ] = match;
    ccType = parsedCcType;

    // Rule 1: Validate length
    if (subjectLine.length > 72) {
        errors.push(`Subject line exceeds 72 characters (${subjectLine.length}/72).`);
    }

    // Rule 2: Validate the Emoji and CC Type against the SOP Matrix
    const validEntry = matrix.find(item => item.emoji === emoji || item.code === emoji);
    if (!validEntry) {
        errors.push(`The emoji '${emoji}' is not in the GitOps SOP.`);
    } else if (validEntry.cc_type !== ccType) {
        errors.push(`Emoji / Type mismatch! According to the SOP, '${emoji}' MUST be paired with type '${validEntry.cc_type}'. You used: '${emoji} ${ccType}'.`);
    }
}

// Full text parsing for Trailers and Included changes
const fullText = lines.join('\n');

// Trailer checks
const hasSemVer = /^SemVer-Impact:\s*(NONE|PATCH|MINOR|MAJOR)$/m.test(fullText);
if (!hasSemVer) {
    errors.push(`Missing or invalid 'SemVer-Impact' trailer. Expected one of: NONE, PATCH, MINOR, MAJOR.`);
}

const validCcTypes = ['build', 'chore', 'ci', 'docs', 'feat', 'fix', 'init', 'perf', 'refactor', 'release', 'revert', 'style', 'test'];
const changeTypesMatch = fullText.match(/^Change-Types:\s*(.+)$/m);
if (!changeTypesMatch) {
    errors.push(`Missing 'Change-Types' trailer. Expected one or more of: ${validCcTypes.join(', ')}.`);
} else {
    const providedTypes = changeTypesMatch[1].split(',').map(t => t.trim());
    const invalidTypes = providedTypes.filter(t => !validCcTypes.includes(t));
    if (invalidTypes.length > 0) {
        errors.push(`Invalid 'Change-Types' provided: ${invalidTypes.join(', ')}. Expected one or more of: ${validCcTypes.join(', ')}.`);
    }
}

const validGroups = ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security', 'Miscellaneous'];
const changelogGroupsMatch = fullText.match(/^Changelog-Groups:\s*(.+)$/m);
if (!changelogGroupsMatch) {
    errors.push(`Missing 'Changelog-Groups' trailer. Expected one or more of: ${validGroups.join(', ')}.`);
} else {
    const providedGroups = changelogGroupsMatch[1].split(',').map(t => t.trim());
    const invalidGroups = providedGroups.filter(g => !validGroups.includes(g));
    if (invalidGroups.length > 0) {
        errors.push(`Invalid 'Changelog-Groups' provided: ${invalidGroups.join(', ')}. Expected one or more of: ${validGroups.join(', ')}.`);
    }
}

// Conditional Ref enforcement
const refRegex = /^(Resolves|Refs|Closes|Fixes):\s*#\S+/m;
const hasRef = refRegex.test(fullText);

const strictRefTypes = ['feat', 'fix', 'perf', 'security', 'lock'];
if (strictRefTypes.includes(ccType) && !hasRef) {
    errors.push(`Missing Issue Reference. Because the commit type is '${ccType}', a trailer like 'Refs: #<issue>' is STRICTLY REQUIRED.`);
}

// Contiguous Trailer Block Check
const blocks = fullText.trim().split(/\n\s*\n/);
const lastBlock = blocks[blocks.length - 1];
const requiredTrailers = ['SemVer-Impact:', 'Change-Types:', 'Changelog-Groups:'];
const hasAllTrailersInLastBlock = requiredTrailers.every(t => lastBlock.includes(t));

if (!hasAllTrailersInLastBlock) {
    errors.push(`Git Trailers must be a single contiguous block at the absolute end of the commit message (no empty lines between them).`);
}

// Check "Included changes:" syntax if present
const includedChangesMatch = fullText.match(/^Included changes:\n((?:- .+\n?)+)/m);
if (includedChangesMatch) {
    const changesLines = includedChangesMatch[1].trim().split('\n');
    changesLines.forEach(line => {
        const itemMatch = line.match(/^- ((?:\p{Emoji_Presentation}|\p{Extended_Pictographic})\uFE0F?|:[a-z0-9_+\-]+:)\s+([a-z]+)(?:\(([a-z0-9\-,\s]+)\))?(!?):\s+(.+)$/u);
        if (!itemMatch) {
            errors.push(`Invalid 'Included changes' item format: '${line}'. Must match '- <emoji> <cc_type>(<scope>): <subject>'.`);
        }
    });
}

// Print errors and exit if any
if (errors.length > 0) {
    console.error(`\n[AI_CORRECTION_REQUIRED]: Your commit message failed validation for the following reasons:\n`);
    errors.forEach(err => console.error(`- ${err}`));
    
    console.error(`\nStandard Expected Format:`);
    console.error(`========================`);
    console.error(`<emoji> <type>(<scope>): <subject>`);
    console.error(`<empty line>`);
    console.error(`<body text>`);
    console.error(`<empty line>`);
    console.error(`Included changes:`);
    console.error(`- <emoji> <type>(<scope>): <subject>`);
    console.error(`<empty line>`);
    console.error(`Resolves: #<issue>`);
    console.error(`SemVer-Impact: <NONE | PATCH | MINOR | MAJOR>`);
    console.error(`Change-Types: <types>`);
    console.error(`Changelog-Groups: <Added | Changed | Deprecated | Removed | Fixed | Security | Miscellaneous>`);
    console.error(`========================\n`);
    process.exit(1);
}

console.log(`\n✅ Commit Validated Successfully.\n`);
process.exit(0);
