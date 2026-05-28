/**
 * Problem 47: Compare Version Numbers
 * 
 * Compare two version strings (e.g., "1.01" vs "1.001").
 * 
 * Approach: Two pointers parse each revision number between dots.
 * Time: O(max(m,n)), Space: O(1)
 * 
 * Production Analogy: Like semantic version comparison in a package manager
 * to determine upgrade paths.
 */
public class Problem47_CompareVersionNumbers {
    public static int compareVersion(String version1, String version2) {
        int i = 0, j = 0;
        while (i < version1.length() || j < version2.length()) {
            int v1 = 0, v2 = 0;
            while (i < version1.length() && version1.charAt(i) != '.') v1 = v1 * 10 + (version1.charAt(i++) - '0');
            while (j < version2.length() && version2.charAt(j) != '.') v2 = v2 * 10 + (version2.charAt(j++) - '0');
            if (v1 < v2) return -1;
            if (v1 > v2) return 1;
            i++; j++;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(compareVersion("1.01", "1.001")); // 0
        System.out.println(compareVersion("1.0", "1.0.0")); // 0
        System.out.println(compareVersion("0.1", "1.1")); // -1
        System.out.println(compareVersion("1.0.1", "1")); // 1
    }
}
