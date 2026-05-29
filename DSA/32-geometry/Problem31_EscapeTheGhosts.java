import java.util.*;

public class Problem31_EscapeTheGhosts {
    public static boolean escapeGhosts(int[][] ghosts, int[] target) {
        int myDist = Math.abs(target[0]) + Math.abs(target[1]);
        for (int[] g : ghosts) if (Math.abs(g[0]-target[0]) + Math.abs(g[1]-target[1]) <= myDist) return false;
        return true;
    }
    public static void main(String[] args) {
        System.out.println(escapeGhosts(new int[][]{{1,0},{0,3}}, new int[]{0,1})); // true
    }
}
