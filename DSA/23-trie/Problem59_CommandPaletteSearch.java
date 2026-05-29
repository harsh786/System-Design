import java.util.*;

/**
 * Problem 59: Command Palette Search (VS Code style)
 * 
 * Production Relevance:
 * - VS Code Cmd+Shift+P, Slack Cmd+K, Spotlight: instant command search
 * - Substring matching + fuzzy matching + frecency scoring
 * - Must handle 1000s of commands with <16ms response time (60fps)
 * - Used in every modern IDE, Electron app, SaaS product
 * 
 * Architect Considerations:
 * - Multi-signal scoring: character match, contiguity, word boundary, recency
 * - Subsequence matching: "ocf" matches "Open Config File"
 * - Index update on command registration/plugin load
 * - Highlight matched characters in UI for user feedback
 */
public class Problem59_CommandPaletteSearch {

    static class Command {
        String id;
        String label;
        String category;
        String shortcut;

        Command(String id, String label, String category, String shortcut) {
            this.id = id; this.label = label; this.category = category; this.shortcut = shortcut;
        }
    }

    static class MatchResult {
        Command command;
        double score;
        List<Integer> matchedIndices; // for highlighting

        MatchResult(Command cmd, double score, List<Integer> indices) {
            this.command = cmd; this.score = score; this.matchedIndices = indices;
        }

        String highlighted() {
            char[] chars = command.label.toCharArray();
            StringBuilder sb = new StringBuilder();
            Set<Integer> matchSet = new HashSet<>(matchedIndices);
            for (int i = 0; i < chars.length; i++) {
                if (matchSet.contains(i)) sb.append('[').append(chars[i]).append(']');
                else sb.append(chars[i]);
            }
            return sb.toString();
        }
    }

    static class CommandPalette {
        List<Command> commands = new ArrayList<>();
        Map<String, Integer> usageCount = new HashMap<>();
        Map<String, Long> lastUsed = new HashMap<>();

        void register(Command cmd) { commands.add(cmd); }

        void recordUsage(String cmdId) {
            usageCount.merge(cmdId, 1, Integer::sum);
            lastUsed.put(cmdId, System.currentTimeMillis());
        }

        List<MatchResult> search(String query, int topK) {
            if (query.isEmpty()) {
                // Return most recently used
                List<MatchResult> recent = new ArrayList<>();
                commands.stream()
                        .sorted((a, b) -> Long.compare(lastUsed.getOrDefault(b.id, 0L), lastUsed.getOrDefault(a.id, 0L)))
                        .limit(topK)
                        .forEach(c -> recent.add(new MatchResult(c, 0, List.of())));
                return recent;
            }

            String lowerQuery = query.toLowerCase();
            List<MatchResult> results = new ArrayList<>();

            for (Command cmd : commands) {
                MatchResult result = scoreMatch(cmd, lowerQuery);
                if (result != null) results.add(result);
            }

            results.sort((a, b) -> Double.compare(b.score, a.score));
            return results.subList(0, Math.min(topK, results.size()));
        }

        private MatchResult scoreMatch(Command cmd, String query) {
            String target = cmd.label.toLowerCase();
            List<Integer> indices = new ArrayList<>();

            // Subsequence matching
            int qi = 0;
            for (int ti = 0; ti < target.length() && qi < query.length(); ti++) {
                if (target.charAt(ti) == query.charAt(qi)) {
                    indices.add(ti);
                    qi++;
                }
            }
            if (qi < query.length()) return null; // Not all query chars matched

            // Scoring
            double score = 0;

            // Contiguity bonus: consecutive matches score higher
            for (int i = 1; i < indices.size(); i++) {
                if (indices.get(i) == indices.get(i - 1) + 1) score += 5;
            }

            // Word boundary bonus: matching at start of words
            for (int idx : indices) {
                if (idx == 0 || target.charAt(idx - 1) == ' ' || target.charAt(idx - 1) == '.') score += 10;
                if (Character.isUpperCase(cmd.label.charAt(idx))) score += 3; // CamelCase boundary
            }

            // Prefix bonus
            if (indices.get(0) == 0) score += 15;

            // Compact match bonus (less spread = better)
            int spread = indices.get(indices.size() - 1) - indices.get(0);
            score += Math.max(0, 20 - spread);

            // Frecency: usage frequency + recency
            score += usageCount.getOrDefault(cmd.id, 0) * 2;
            Long last = lastUsed.get(cmd.id);
            if (last != null) score += 10.0 / (1 + (System.currentTimeMillis() - last) / 60000.0);

            return new MatchResult(cmd, score, indices);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Command Palette Search (VS Code style) ===\n");

        CommandPalette palette = new CommandPalette();
        palette.register(new Command("file.open", "Open File", "File", "Cmd+O"));
        palette.register(new Command("file.save", "Save File", "File", "Cmd+S"));
        palette.register(new Command("file.openRecent", "Open Recent File", "File", ""));
        palette.register(new Command("edit.find", "Find in File", "Edit", "Cmd+F"));
        palette.register(new Command("edit.replace", "Find and Replace", "Edit", "Cmd+H"));
        palette.register(new Command("view.terminal", "Toggle Terminal", "View", "Ctrl+`"));
        palette.register(new Command("git.commit", "Git: Commit", "Git", ""));
        palette.register(new Command("git.push", "Git: Push", "Git", ""));
        palette.register(new Command("debug.start", "Start Debugging", "Debug", "F5"));
        palette.register(new Command("format.document", "Format Document", "Format", "Shift+Alt+F"));

        // User frequently uses "Open File"
        palette.recordUsage("file.open");
        palette.recordUsage("file.open");
        palette.recordUsage("file.open");

        String[] queries = {"of", "open", "git", "ff", "term", "fir"};
        for (String q : queries) {
            System.out.printf("Query: \"%s\"%n", q);
            List<MatchResult> results = palette.search(q, 3);
            for (MatchResult r : results) {
                System.out.printf("  %.1f  %s  [%s]%n", r.score, r.highlighted(), r.command.category);
            }
            System.out.println();
        }
    }
}
