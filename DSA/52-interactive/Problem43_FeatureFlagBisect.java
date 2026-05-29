import java.util.*;

public class Problem43_FeatureFlagBisect {
    // Bisect which feature flag caused a regression
    static String[] flags = {"flagA","flagB","flagC","flagD","flagE"};
    static String badFlag = "flagC";
    
    static boolean testWithFlags(Set<String> enabled) {
        return !enabled.contains(badFlag); // passes if bad flag not enabled
    }
    
    static String bisectFlags() {
        int lo = 0, hi = flags.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            Set<String> enabled = new HashSet<>();
            for (int i = lo; i <= mid; i++) enabled.add(flags[i]);
            if (!testWithFlags(enabled)) hi = mid;
            else lo = mid + 1;
        }
        return flags[lo];
    }
    
    public static void main(String[] args) {
        System.out.println("Bad flag: " + bisectFlags()); // flagC
    }
}
