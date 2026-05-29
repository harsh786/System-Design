import java.util.*;

public class Problem14_SmallestSufficientTeam {
    public int[] smallestSufficientTeam(String[] reqSkills, List<List<String>> people) {
        int n = reqSkills.length, m = people.size();
        Map<String, Integer> skillIdx = new HashMap<>();
        for (int i = 0; i < n; i++) skillIdx.put(reqSkills[i], i);
        int[] personMask = new int[m];
        for (int i = 0; i < m; i++) for (String s : people.get(i)) if (skillIdx.containsKey(s)) personMask[i] |= (1 << skillIdx.get(s));
        long[] dp = new long[1 << n];
        Arrays.fill(dp, (1L << m) - 1);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            for (int i = 0; i < m; i++) {
                int next = mask | personMask[i];
                long team = dp[mask] | (1L << i);
                if (Long.bitCount(team) < Long.bitCount(dp[next])) dp[next] = team;
            }
        }
        long team = dp[(1 << n) - 1];
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < m; i++) if ((team & (1L << i)) != 0) result.add(i);
        return result.stream().mapToInt(Integer::intValue).toArray();
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem14_SmallestSufficientTeam().smallestSufficientTeam(
            new String[]{"java","nodejs","reactjs"},
            Arrays.asList(Arrays.asList("java"), Arrays.asList("nodejs"), Arrays.asList("nodejs","reactjs")))));
    }
}
