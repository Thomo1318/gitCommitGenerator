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

// Read and clean the commit message (ignore comments)
const rawMsg = fs.readFileSync(commitMsgFile, 'utf8');
const lines = rawMsg.split('\n').filter(line => !line.trim().startsWith('#'));
if (lines.length === 0) process.exit(0);

const subjectLine = lines[0].trim();

// Regex to capture: Emoji (unicode or shortcode), CC Type, Scope (optional), Breaking (!), and Subject
// Example match: "✨ feat(auth)!: add login" -> ["✨", "feat", "auth", "!", "add login"]
// Example match: ":sparkles: feat(auth)!: add login" -> [":sparkles:", "feat", "auth", "!", "add login"]
const commitRegex = /^(\p{Emoji_Presentation}|\p{Extended_Pictographic}|:[a-z0-9_+\-]+:)\s+([a-z]+)(?:\(([a-z0-9\-,\s]+)\))?(!?):\s+(.+)$/u;

const match = subjectLine.match(commitRegex);

if (!match) {
    console.error(`\n❌ COMMIT FAILED: Invalid Hybrid Syntax.`);
    console.error(`Expected: <emoji> <cc_type>(<scope>): <subject>`);
    console.error(`Received: ${subjectLine}\n`);
    process.exit(1);
}

const [ , emoji, ccType, scope, breaking, subject ] = match;

// Rule 1: Validate length
if (subjectLine.length > 72) {
    console.error(`\n❌ COMMIT FAILED: Subject line exceeds 72 characters (${subjectLine.length}/72).\n`);
    process.exit(1);
}

// Rule 2: Validate the Emoji and CC Type against the SOP Matrix
const validEntry = matrix.find(item => item.emoji === emoji || item.code === emoji);

if (!validEntry) {
    console.error(`\n❌ COMMIT FAILED: The emoji '${emoji}' is not in the GitOps SOP.\n`);
    process.exit(1);
}

if (validEntry.cc_type !== ccType) {
    console.error(`\n❌ COMMIT FAILED: Emoji / Type mismatch!`);
    console.error(`According to the SOP, '${emoji}' MUST be paired with type '${validEntry.cc_type}'.`);
    console.error(`You used: '${emoji} ${ccType}'.\n`);
    process.exit(1);
}

console.log(`\n✅ Commit Validated: ${validEntry.semver_impact} impact detected.\n`);
process.exit(0);
