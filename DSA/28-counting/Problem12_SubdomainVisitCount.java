/**
 * Problem: Subdomain Visit Count (LeetCode 811)
 * Approach: Parse and accumulate counts for all domain levels
 * Complexity: O(n * L) time where L=domain length
 * Production Analogy: Web analytics domain aggregation, DNS query counting
 */
import java.util.*;
public class Problem12_SubdomainVisitCount {
    public List<String> subdomainVisits(String[] cpdomains) {
        Map<String, Integer> map = new HashMap<>();
        for (String cp : cpdomains) {
            String[] parts = cp.split(" ");
            int count = Integer.parseInt(parts[0]);
            String domain = parts[1];
            for (int i = 0; i < domain.length(); i++) {
                if (i == 0 || domain.charAt(i-1) == '.')
                    map.merge(domain.substring(i), count, Integer::sum);
            }
        }
        List<String> res = new ArrayList<>();
        for (var e : map.entrySet()) res.add(e.getValue() + " " + e.getKey());
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new Problem12_SubdomainVisitCount().subdomainVisits(
            new String[]{"9001 discuss.leetcode.com"}));
    }
}
