import java.util.*;

/**
 * Problem 27: Subdomain Visit Count
 * Given count-paired domains like "9001 discuss.leetcode.com", compute visit counts
 * for all subdomains.
 *
 * Time Complexity: O(n * L) where L is domain length
 * Space Complexity: O(n * L)
 *
 * Production Analogy: Like DNS analytics aggregation - counting hits at every level
 * of the domain hierarchy for traffic analysis.
 */
public class Problem27_SubdomainVisitCount {
    public List<String> subdomainVisits(String[] cpdomains) {
        Map<String, Integer> counts = new HashMap<>();
        for (String cp : cpdomains) {
            String[] parts = cp.split(" ");
            int count = Integer.parseInt(parts[0]);
            String domain = parts[1];
            counts.merge(domain, count, Integer::sum);
            for (int i = 0; i < domain.length(); i++) {
                if (domain.charAt(i) == '.') {
                    counts.merge(domain.substring(i + 1), count, Integer::sum);
                }
            }
        }
        List<String> result = new ArrayList<>();
        for (var e : counts.entrySet()) result.add(e.getValue() + " " + e.getKey());
        return result;
    }

    public static void main(String[] args) {
        Problem27_SubdomainVisitCount sol = new Problem27_SubdomainVisitCount();
        System.out.println(sol.subdomainVisits(new String[]{"9001 discuss.leetcode.com"}));
        System.out.println(sol.subdomainVisits(new String[]{"900 google.mail.com", "50 yahoo.com", "1 intel.mail.com", "5 wiki.org"}));
    }
}
