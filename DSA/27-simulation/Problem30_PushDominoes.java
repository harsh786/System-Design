/**
 * Problem: Push Dominoes (LeetCode 838)
 * Approach: Two-pass force simulation (left and right forces)
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Bidirectional propagation in event-driven systems
 */
public class Problem30_PushDominoes {
    public String pushDominoes(String dominoes) {
        int n = dominoes.length();
        int[] forces = new int[n];
        int force = 0;
        for (int i = 0; i < n; i++) {
            if (dominoes.charAt(i)=='R') force = n;
            else if (dominoes.charAt(i)=='L') force = 0;
            else force = Math.max(force-1, 0);
            forces[i] += force;
        }
        force = 0;
        for (int i = n-1; i >= 0; i--) {
            if (dominoes.charAt(i)=='L') force = n;
            else if (dominoes.charAt(i)=='R') force = 0;
            else force = Math.max(force-1, 0);
            forces[i] -= force;
        }
        StringBuilder sb = new StringBuilder();
        for (int f : forces) sb.append(f > 0 ? 'R' : (f < 0 ? 'L' : '.'));
        return sb.toString();
    }
    public static void main(String[] args) {
        System.out.println(new Problem30_PushDominoes().pushDominoes(".L.R...LR..L..")); // LL.RR.LLRRLL..
    }
}
