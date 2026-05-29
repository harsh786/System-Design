import java.util.*;

public class Problem03_FindCelebrity {
    static boolean[][] knows;
    
    static boolean knows(int a, int b) { return knows[a][b]; }
    
    static int findCelebrity(int n) {
        int candidate = 0;
        for (int i = 1; i < n; i++) {
            if (knows(candidate, i)) candidate = i;
        }
        for (int i = 0; i < n; i++) {
            if (i != candidate) {
                if (knows(candidate, i) || !knows(i, candidate)) return -1;
            }
        }
        return candidate;
    }
    
    public static void main(String[] args) {
        knows = new boolean[][] {
            {true, true, true},
            {false, true, true},
            {false, false, true}
        };
        System.out.println("Celebrity: " + findCelebrity(3)); // 2
    }
}
