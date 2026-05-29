import java.util.*;

public class Problem44_DeploymentRegressionBisect {
    static String[] commits = {"a1","b2","c3","d4","e5","f6","g7","h8"};
    static int badCommitIdx = 4; // e5 introduced bug
    
    static boolean testCommit(int idx) { return idx < badCommitIdx; }
    
    static String gitBisect() {
        int lo = 0, hi = commits.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (testCommit(mid)) lo = mid + 1;
            else hi = mid;
        }
        return commits[lo];
    }
    
    public static void main(String[] args) {
        System.out.println("First bad commit: " + gitBisect()); // e5
    }
}
