import java.util.*;

public class Problem10_JudgeAPICelebrity {
    // Celebrity problem with explicit Judge API
    static int celebrity = 2;
    static int n = 5;
    static int queryCnt = 0;
    
    static boolean knows(int a, int b) {
        queryCnt++;
        if (b == celebrity) return true;
        if (a == celebrity) return false;
        return new Random(a * 100 + b).nextBoolean();
    }
    
    static int findCelebrity() {
        int cand = 0;
        for (int i = 1; i < n; i++) if (knows(cand, i)) cand = i;
        for (int i = 0; i < n; i++) {
            if (i != cand && (knows(cand, i) || !knows(i, cand))) return -1;
        }
        return cand;
    }
    
    public static void main(String[] args) {
        System.out.println("Celebrity: " + findCelebrity() + " queries=" + queryCnt);
    }
}
