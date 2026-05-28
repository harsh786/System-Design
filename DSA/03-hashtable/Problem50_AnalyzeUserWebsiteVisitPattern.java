import java.util.*;

/**
 * Problem 50: Analyze User Website Visit Pattern
 * Find the 3-website sequence visited by the most users.
 *
 * Approach:
 * 1. Group visits by user, sort by timestamp.
 * 2. For each user, enumerate all 3-combinations of their websites (maintain order).
 * 3. Count unique users per 3-sequence pattern. Return lexicographically smallest max.
 *
 * Time Complexity: O(n^3) per user in worst case (but bounded by user's visit count)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like clickstream analysis in product analytics (Amplitude, Mixpanel).
 * Finding the most common user journey (funnel pattern) across all users.
 */
public class Problem50_AnalyzeUserWebsiteVisitPattern {
    public List<String> mostVisitedPattern(String[] username, int[] timestamp, String[] website) {
        // Group by user with timestamp ordering
        Map<String, List<int[]>> userVisits = new HashMap<>();
        for (int i = 0; i < username.length; i++) {
            userVisits.computeIfAbsent(username[i], k -> new ArrayList<>()).add(new int[]{timestamp[i], i});
        }

        Map<String, Integer> patternCount = new HashMap<>();
        for (var entry : userVisits.entrySet()) {
            List<int[]> visits = entry.getValue();
            visits.sort((a, b) -> a[0] - b[0]);
            // Generate all 3-combinations, deduplicate per user
            Set<String> patterns = new HashSet<>();
            for (int i = 0; i < visits.size(); i++)
                for (int j = i + 1; j < visits.size(); j++)
                    for (int k = j + 1; k < visits.size(); k++) {
                        String pat = website[visits.get(i)[1]] + "#" +
                                     website[visits.get(j)[1]] + "#" +
                                     website[visits.get(k)[1]];
                        patterns.add(pat);
                    }
            for (String p : patterns) patternCount.merge(p, 1, Integer::sum);
        }

        String bestPattern = "";
        int maxCount = 0;
        for (var e : patternCount.entrySet()) {
            if (e.getValue() > maxCount || (e.getValue() == maxCount && e.getKey().compareTo(bestPattern) < 0)) {
                maxCount = e.getValue();
                bestPattern = e.getKey();
            }
        }
        return Arrays.asList(bestPattern.split("#"));
    }

    public static void main(String[] args) {
        Problem50_AnalyzeUserWebsiteVisitPattern sol = new Problem50_AnalyzeUserWebsiteVisitPattern();
        String[] users = {"joe","joe","joe","james","james","james","james","mary","mary","mary"};
        int[] times = {1,2,3,4,5,6,7,8,9,10};
        String[] sites = {"home","about","career","home","cart","maps","home","home","about","career"};
        System.out.println(sol.mostVisitedPattern(users, times, sites)); // [home, about, career]
    }
}
