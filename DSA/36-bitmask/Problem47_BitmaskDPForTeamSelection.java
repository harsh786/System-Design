import java.util.Arrays;

public class Problem47_BitmaskDPForTeamSelection {
    // Select teams maximizing total skill with constraints
    public int maxTeamSkill(int[] skills, int[][] conflicts, int teamSize) {
        int n = skills.length;
        int[] conflictMask = new int[n];
        for (int[] c : conflicts) { conflictMask[c[0]] |= (1 << c[1]); conflictMask[c[1]] |= (1 << c[0]); }
        int max = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (Integer.bitCount(mask) != teamSize) continue;
            boolean valid = true;
            for (int i = 0; i < n && valid; i++)
                if ((mask & (1 << i)) != 0 && (mask & conflictMask[i]) != 0) valid = false;
            if (valid) {
                int sum = 0;
                for (int i = 0; i < n; i++) if ((mask & (1 << i)) != 0) sum += skills[i];
                max = Math.max(max, sum);
            }
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(new Problem47_BitmaskDPForTeamSelection().maxTeamSkill(
            new int[]{5,4,3,2,1}, new int[][]{{0,1},{2,3}}, 3)); // 5+3+1=9 or 5+2+1=8... depends
    }
}
