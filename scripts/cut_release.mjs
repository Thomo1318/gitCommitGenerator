import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sopPath = path.resolve(__dirname, '../config/gitops_agent_sop.json');
const sop = JSON.parse(fs.readFileSync(sopPath, 'utf8'));

console.log("🚀 Starting Release Engine...");

// 1. Get the last git tag
let lastTag;
try {
    lastTag = execSync('git describe --tags --abbrev=0').toString().trim();
} catch (e) {
    console.log("No previous tags found. Assuming v0.0.0");
    lastTag = "v0.0.0";
}

// 2. Get commits since last tag
const logCmd = lastTag === "v0.0.0" ? `git log --pretty=format:"%s"` : `git log ${lastTag}..HEAD --pretty=format:"%s"`;
const commits = execSync(logCmd).toString().trim().split('\n').filter(Boolean);

if (commits.length === 0) {
    console.log("No new commits to release.");
    process.exit(0);
}

let bumpType = "PATCH"; // Default to patch
const changelogData = {};

// Initialize changelog groups based on SOP
sop.changelog_generation_rules.taxonomy.forEach(tax => {
    const group = tax.split(':')[0];
    changelogData[group] = [];
});

// 3. Parse Commits & Determine SemVer Impact
commits.forEach(commit => {
    const match = commit.match(/^(\p{Emoji_Presentation}|\p{Extended_Pictographic})\s+([a-z]+)/u);
    if (!match) return;

    const emoji = match[1];
    const matrixEntry = sop.gitmoji_reference_matrix.find(m => m.emoji === emoji);
    
    if (matrixEntry) {
        // Evaluate SemVer Bump
        if (matrixEntry.semver_impact === "MAJOR" || commit.includes("!:")) bumpType = "MAJOR";
        if (matrixEntry.semver_impact === "MINOR" && bumpType !== "MAJOR") bumpType = "MINOR";
        
        // Group for Changelog
        if (changelogData[matrixEntry.changelog_group]) {
            changelogData[matrixEntry.changelog_group].push(`- ${commit}`);
        }
    }
});

// 4. Calculate New Version (Simple SemVer parser)
let [major, minor, patch] = lastTag.replace('v', '').split('.').map(Number);

if (bumpType === "MAJOR") { major++; minor = 0; patch = 0; }
else if (bumpType === "MINOR") { minor++; patch = 0; }
else { patch++; }

const newVersion = `${major}.${minor}.${patch}`;
console.log(`\n📦 Calculated Bump: ${bumpType} (${lastTag} -> v${newVersion})`);

// 5. Inject Version (Executing the version_injection_matrix for JSON as an example)
const pkgPath = path.resolve(__dirname, '../package.json');
if (fs.existsSync(pkgPath)) {
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
    pkg.version = newVersion;
    fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');
    console.log(`✅ Injected v${newVersion} into package.json`);
}

// 6. Generate Changelog markdown
let releaseNotes = `\n## [v${newVersion}] - ${new Date().toISOString().split('T')[0]}\n\n`;

for (const [group, items] of Object.entries(changelogData)) {
    if (items.length > 0) {
        releaseNotes += `### ${group}\n${items.join('\n')}\n\n`;
    }
}

const clPath = path.resolve(__dirname, '../CHANGELOG.md');
const existingCL = fs.existsSync(clPath) ? fs.readFileSync(clPath, 'utf8') : "# Changelog\n";
fs.writeFileSync(clPath, existingCL.replace("# Changelog\n", `# Changelog\n${releaseNotes}`));

console.log(`✅ Appended release notes to CHANGELOG.md`);
console.log(`\n🎯 Release artifacts generated successfully! Run the following commands to finalize:\n`);
console.log(`git add package.json CHANGELOG.md`);
console.log(`git commit -m "🔖 release: v${newVersion}"`);
console.log(`git tag -a v${newVersion} -m "Release v${newVersion}"`);
console.log(`git push --follow-tags`);
