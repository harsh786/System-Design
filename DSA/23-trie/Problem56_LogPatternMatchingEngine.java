import java.util.*;

/**
 * Problem 56: Log Pattern Matching Engine
 * 
 * Production Relevance:
 * - Log aggregation systems (Datadog, Splunk, ELK) parse unstructured logs into patterns
 * - Pattern clustering: group similar log lines to reduce noise
 * - Drain algorithm: tree-based online log parsing
 * - Enables: anomaly detection, log-based alerting, structured extraction
 * 
 * Architect Considerations:
 * - Online algorithm: must process logs as they stream (no second pass)
 * - Token-based trie where variables become wildcards <*>
 * - Similarity threshold determines when to create new pattern vs match existing
 * - Memory: bounded number of patterns (merge similar ones)
 */
public class Problem56_LogPatternMatchingEngine {

    static class LogPattern {
        List<String> tokens; // mix of literal tokens and "<*>" wildcards
        int matchCount;
        long lastSeen;

        LogPattern(List<String> tokens) {
            this.tokens = new ArrayList<>(tokens);
            this.matchCount = 1;
            this.lastSeen = System.currentTimeMillis();
        }

        String toPattern() { return String.join(" ", tokens); }
    }

    static class PatternNode {
        Map<String, PatternNode> children = new HashMap<>();
        LogPattern pattern;
    }

    static class LogPatternEngine {
        PatternNode root = new PatternNode();
        double similarityThreshold = 0.5;
        List<LogPattern> patterns = new ArrayList<>();
        Map<String, Set<String>> tokenIndex = new HashMap<>(); // for fast lookup

        // Process a log line, return matched or new pattern
        LogPattern process(String logLine) {
            List<String> tokens = tokenize(logLine);
            int length = tokens.size();

            // Find best matching pattern of same length
            LogPattern bestMatch = null;
            double bestSim = 0;

            for (LogPattern existing : patterns) {
                if (existing.tokens.size() != length) continue;
                double sim = similarity(tokens, existing.tokens);
                if (sim > bestSim) { bestSim = sim; bestMatch = existing; }
            }

            if (bestMatch != null && bestSim >= similarityThreshold) {
                // Merge: positions that differ become <*>
                for (int i = 0; i < length; i++) {
                    if (!tokens.get(i).equals(bestMatch.tokens.get(i))) {
                        bestMatch.tokens.set(i, "<*>");
                    }
                }
                bestMatch.matchCount++;
                bestMatch.lastSeen = System.currentTimeMillis();
                return bestMatch;
            }

            // No match: create new pattern
            LogPattern newPattern = new LogPattern(tokens);
            patterns.add(newPattern);
            return newPattern;
        }

        private double similarity(List<String> a, List<String> b) {
            int matches = 0;
            for (int i = 0; i < a.size(); i++) {
                if (a.get(i).equals(b.get(i)) || b.get(i).equals("<*>")) matches++;
            }
            return (double) matches / a.size();
        }

        private List<String> tokenize(String line) {
            // Simple tokenization: split on spaces, numbers become wildcards
            String[] raw = line.split("\\s+");
            List<String> tokens = new ArrayList<>();
            for (String t : raw) {
                if (t.matches("\\d+") || t.matches("\\d+\\.\\d+") ||
                    t.matches("[0-9a-f]{8,}") || t.matches("\\d{4}-\\d{2}-\\d{2}.*")) {
                    tokens.add("<*>");
                } else {
                    tokens.add(t);
                }
            }
            return tokens;
        }

        void printPatterns() {
            patterns.sort((a, b) -> Integer.compare(b.matchCount, a.matchCount));
            for (LogPattern p : patterns) {
                System.out.printf("  [%3dx] %s%n", p.matchCount, p.toPattern());
            }
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Log Pattern Matching Engine ===\n");

        LogPatternEngine engine = new LogPatternEngine();

        String[] logs = {
            "Connection from 192.168.1.5 port 443 established",
            "Connection from 10.0.0.3 port 8080 established",
            "Connection from 172.16.0.1 port 443 established",
            "User alice logged in from 192.168.1.5",
            "User bob logged in from 10.0.0.3",
            "Error processing request 12345: timeout after 30s",
            "Error processing request 67890: timeout after 45s",
            "Error processing request 11111: connection refused",
            "Health check passed for service auth-service",
            "Health check passed for service user-service",
        };

        System.out.println("Processing logs:");
        for (String log : logs) {
            LogPattern pattern = engine.process(log);
            System.out.printf("  \"%s\"%n    -> %s%n", log, pattern.toPattern());
        }

        System.out.println("\nDiscovered patterns:");
        engine.printPatterns();
    }
}
