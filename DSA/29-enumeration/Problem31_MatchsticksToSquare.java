import java.util.Arrays;

public class Problem31_MatchsticksToSquare {
    public boolean makesquare(int[] matchsticks) {
        int sum = Arrays.stream(matchsticks).sum();
        if (sum % 4 != 0) return false;
        int side = sum / 4;
        Arrays.sort(matchsticks);
        return dfs(matchsticks, new int[4], matchsticks.length-1, side);
    }
    private boolean dfs(int[] m, int[] sides, int idx, int target) {
        if (idx < 0) return true;
        for (int i = 0; i < 4; i++) {
            if (sides[i]+m[idx]>target) continue;
            if (i > 0 && sides[i]==sides[i-1]) continue;
            sides[i]+=m[idx]; if (dfs(m,sides,idx-1,target)) return true; sides[i]-=m[idx];
        }
        return false;
    }
    public static void main(String[] args) { System.out.println(new Problem31_MatchsticksToSquare().makesquare(new int[]{1,1,2,2,2})); }
}
