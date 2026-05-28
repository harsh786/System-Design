/**
 * Problem 44: Push Dominoes
 * 
 * Given string with 'L', 'R', '.', determine final state after all dominoes fall.
 * 
 * Approach: Two pointers - find segments between L/R forces and fill accordingly.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like propagating configuration changes from both edges
 * of a service mesh and resolving conflicts in the middle.
 */
public class Problem44_PushDominoes {
    public static String pushDominoes(String dominoes) {
        char[] d = dominoes.toCharArray();
        int n = d.length;
        int[] forces = new int[n];
        int force = 0;
        // Left to right: R forces
        for (int i = 0; i < n; i++) {
            if (d[i] == 'R') force = n;
            else if (d[i] == 'L') force = 0;
            else force = Math.max(force - 1, 0);
            forces[i] += force;
        }
        // Right to left: L forces
        force = 0;
        for (int i = n - 1; i >= 0; i--) {
            if (d[i] == 'L') force = n;
            else if (d[i] == 'R') force = 0;
            else force = Math.max(force - 1, 0);
            forces[i] -= force;
        }
        StringBuilder sb = new StringBuilder();
        for (int f : forces) sb.append(f > 0 ? 'R' : (f < 0 ? 'L' : '.'));
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(pushDominoes("RR.L")); // RR.L
        System.out.println(pushDominoes(".L.R...LR..L..")); // LL.RR.LLRRLL..
    }
}
