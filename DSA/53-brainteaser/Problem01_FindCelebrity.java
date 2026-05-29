import java.util.*;

public class Problem01_FindCelebrity {
    static boolean[][] knows = {{true,true,true},{false,true,true},{false,false,true}};
    static boolean knows(int a, int b) { return knows[a][b]; }
    
    static int findCelebrity(int n) {
        int cand = 0;
        for (int i = 1; i < n; i++) if (knows(cand, i)) cand = i;
        for (int i = 0; i < n; i++)
            if (i != cand && (knows(cand, i) || !knows(i, cand))) return -1;
        return cand;
    }
    
    public static void main(String[] args) { System.out.println("Celebrity: " + findCelebrity(3)); }
}
