import java.util.*;

public class Problem19_24Game {
    // 679. 24 Game: Given 4 cards (1-9), use +,-,*,/ to make 24.
    
    public boolean judgePoint24(int[] cards) {
        List<Double> list = new ArrayList<>();
        for (int c : cards) list.add((double) c);
        return solve(list);
    }
    
    private boolean solve(List<Double> nums) {
        if (nums.size() == 1) return Math.abs(nums.get(0) - 24) < 1e-6;
        for (int i = 0; i < nums.size(); i++) {
            for (int j = 0; j < nums.size(); j++) {
                if (i == j) continue;
                List<Double> next = new ArrayList<>();
                for (int k = 0; k < nums.size(); k++) if (k != i && k != j) next.add(nums.get(k));
                double a = nums.get(i), b = nums.get(j);
                double[] results = {a+b, a-b, a*b};
                for (double r : results) { next.add(r); if (solve(next)) return true; next.remove(next.size()-1); }
                if (Math.abs(b) > 1e-6) { next.add(a/b); if (solve(next)) return true; next.remove(next.size()-1); }
            }
        }
        return false;
    }
    
    public static void main(String[] args) {
        Problem19_24Game sol = new Problem19_24Game();
        System.out.println(sol.judgePoint24(new int[]{4,1,8,7})); // true (8*(7-4+1)=24? or (8-4)*(7-1))
        System.out.println(sol.judgePoint24(new int[]{1,2,1,2})); // false
    }
}
