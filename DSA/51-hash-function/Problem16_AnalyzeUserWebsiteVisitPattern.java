import java.util.*;

public class Problem16_AnalyzeUserWebsiteVisitPattern {
    public List<String> mostVisitedPattern(String[] username, int[] timestamp, String[] website) {
        int n = username.length;
        Integer[] idx = new Integer[n];
        for (int i = 0; i < n; i++) idx[i] = i;
        Arrays.sort(idx, (a, b) -> timestamp[a] - timestamp[b]);
        Map<String, List<String>> userSites = new HashMap<>();
        for (int i : idx) userSites.computeIfAbsent(username[i], k -> new ArrayList<>()).add(website[i]);
        Map<String, Integer> patternCount = new HashMap<>();
        for (List<String> sites : userSites.values()) {
            Set<String> patterns = new HashSet<>();
            for (int i = 0; i < sites.size(); i++)
                for (int j = i+1; j < sites.size(); j++)
                    for (int k = j+1; k < sites.size(); k++)
                        patterns.add(sites.get(i)+","+sites.get(j)+","+sites.get(k));
            for (String p : patterns) patternCount.merge(p, 1, Integer::sum);
        }
        String best = Collections.max(patternCount.entrySet(), (a,b) -> a.getValue() != b.getValue() ? a.getValue()-b.getValue() : b.getKey().compareTo(a.getKey())).getKey();
        return Arrays.asList(best.split(","));
    }

    public static void main(String[] args) {
        Problem16_AnalyzeUserWebsiteVisitPattern sol = new Problem16_AnalyzeUserWebsiteVisitPattern();
        System.out.println(sol.mostVisitedPattern(
            new String[]{"joe","joe","joe","james","james","james","james","mary","mary","mary"},
            new int[]{1,2,3,4,5,6,7,8,9,10},
            new String[]{"home","about","career","home","cart","maps","home","home","about","career"}));
    }
}
