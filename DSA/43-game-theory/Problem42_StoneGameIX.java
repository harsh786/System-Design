import java.util.*;

public class Problem42_StoneGameIX {
    // 2029. Stone Game IX: Remove stones. Running sum % 3 == 0 means that player loses.
    // Alice wants Bob to lose (or avoid losing herself). Return true if Alice wins.
    
    public boolean stoneGameIX(int[] stones) {
        int[] cnt = new int[3];
        for (int s : stones) cnt[s % 3]++;
        // If Alice picks 1 first, sequence must avoid sum%3==0
        // If Alice picks 2 first, similarly
        return check(cnt[0], cnt[1], cnt[2]) || check(cnt[0], cnt[2], cnt[1]);
    }
    
    private boolean check(int zeros, int ones, int twos) {
        // Alice picks from 'ones' group first. Then alternating 1,2,1,2...
        if (ones == 0) return false;
        ones--;
        int turns = ones + twos; // remaining moves after first
        // After pairing ones and twos: min(ones,twos) pairs consumed
        int pairs = Math.min(ones, twos);
        ones -= pairs; twos -= pairs;
        // Remaining same-type stones must maintain non-zero mod 3
        // zeros flip turn advantage
        if (zeros % 2 == 0) return ones > 0 || twos > 0 || pairs > 0;
        return ones > 2 || twos > 2; // need buffer for zero flips
    }
    
    public static void main(String[] args) {
        Problem42_StoneGameIX sol = new Problem42_StoneGameIX();
        System.out.println(sol.stoneGameIX(new int[]{2,1}));     // true
        System.out.println(sol.stoneGameIX(new int[]{2}));       // false
        System.out.println(sol.stoneGameIX(new int[]{5,1,2,4,3})); // false
    }
}
