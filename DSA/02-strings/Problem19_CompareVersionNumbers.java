import java.util.*;

/**
 * Problem 19: Compare Version Numbers (LeetCode 165)
 * 
 * Approach: Split by '.', compare each revision. O(n+m) time, O(n+m) space.
 * 
 * Production Analogy: Like semver comparison in package managers - each segment
 * has different weight and trailing zeros are insignificant.
 */
public class Problem19_CompareVersionNumbers {

    public static int compareVersion(String version1, String version2) {
        String[] v1 = version1.split("\\.");
        String[] v2 = version2.split("\\.");
        int len = Math.max(v1.length, v2.length);
        for (int i = 0; i < len; i++) {
            int n1 = i < v1.length ? Integer.parseInt(v1[i]) : 0;
            int n2 = i < v2.length ? Integer.parseInt(v2[i]) : 0;
            if (n1 < n2) return -1;
            if (n1 > n2) return 1;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(compareVersion("1.01", "1.001"));   // 0
        System.out.println(compareVersion("1.0", "1.0.0"));    // 0
        System.out.println(compareVersion("0.1", "1.1"));      // -1
        System.out.println(compareVersion("1.0.1", "1"));      // 1
    }
}
