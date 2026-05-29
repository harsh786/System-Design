/**
 * Problem 37: Smallest Sufficient Team
 * Given required skills and people with skill subsets, find smallest team covering all skills.
 * 
 * Approach: Bitmask DP. State = set of skills covered. dp[mask] = smallest team for that mask.
 * Time: O(2^m * n) where m = skills, n = people. Space: O(2^m)
 * 
 * Production Analogy: Minimum team staffing to cover all required competencies.
 */
import java.util.*;

public class Problem37_SmallestSufficientTeam {
    public static int[] smallestSufficientTeam(String[] req_skills, List<List<String>> people) {
        int m = req_skills.length;
        Map<String, Integer> skillIdx = new HashMap<>();
        for (int i = 0; i < m; i++) skillIdx.put(req_skills[i], i);
        
        int n = people.size();
        int[] personMask = new int[n];
        for (int i = 0; i < n; i++)
            for (String s : people.get(i))
                if (skillIdx.containsKey(s))
                    personMask[i] |= 1 << skillIdx.get(s);
        
        int target = (1 << m) - 1;
        List<Integer>[] dp = new List[target + 1];
        dp[0] = new ArrayList<>();
        
        for (int mask = 0; mask <= target; mask++) {
            if (dp[mask] == null) continue;
            for (int i = 0; i < n; i++) {
                int newMask = mask | personMask[i];
                if (dp[newMask] == null || dp[newMask].size() > dp[mask].size() + 1) {
                    dp[newMask] = new ArrayList<>(dp[mask]);
                    dp[newMask].add(i);
                }
            }
        }
        return dp[target].stream().mapToInt(Integer::intValue).toArray();
    }

    public static void main(String[] args) {
        List<List<String>> people = List.of(List.of("java"), List.of("nodejs"), List.of("nodejs","reactjs"));
        int[] r = smallestSufficientTeam(new String[]{"java","nodejs","reactjs"}, people);
        System.out.println(Arrays.toString(r)); // [0, 2]
    }
}
