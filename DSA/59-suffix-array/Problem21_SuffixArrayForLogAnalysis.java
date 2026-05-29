import java.util.*;

public class Problem21_SuffixArrayForLogAnalysis {
    // Find repeated patterns in log text
    public static List<String> findRepeatedPatterns(String log, int minLen) {
        int n = log.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++) sa[i]=i;
        Arrays.sort(sa,(a,b)->log.substring(a).compareTo(log.substring(b)));
        Set<String> patterns = new TreeSet<>();
        for (int i = 1; i < n; i++) {
            int lcp = 0, a = sa[i-1], b = sa[i];
            while(a+lcp<n&&b+lcp<n&&log.charAt(a+lcp)==log.charAt(b+lcp)) lcp++;
            if (lcp >= minLen) patterns.add(log.substring(sa[i], sa[i]+lcp));
        }
        return new ArrayList<>(patterns);
    }

    public static void main(String[] args) {
        String log = "ERROR:disk_full|WARN:mem_low|ERROR:disk_full|INFO:ok|ERROR:disk_full";
        System.out.println(findRepeatedPatterns(log, 5));
    }
}
