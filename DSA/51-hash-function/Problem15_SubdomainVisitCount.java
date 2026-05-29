import java.util.*;

public class Problem15_SubdomainVisitCount {
    public List<String> subdomainVisits(String[] cpdomains) {
        Map<String, Integer> map = new HashMap<>();
        for (String cp : cpdomains) {
            String[] parts = cp.split(" ");
            int count = Integer.parseInt(parts[0]);
            String domain = parts[1];
            String[] frags = domain.split("\\.");
            StringBuilder sb = new StringBuilder();
            for (int i = frags.length - 1; i >= 0; i--) {
                sb.insert(0, (i < frags.length - 1 ? "." : "") + frags[i]);
                if (i < frags.length - 1) sb.insert(0, "");
                String key = "";
                StringBuilder k = new StringBuilder();
                for (int j = i; j < frags.length; j++) { if (j > i) k.append("."); k.append(frags[j]); }
                map.merge(k.toString(), count, Integer::sum);
            }
        }
        List<String> result = new ArrayList<>();
        for (Map.Entry<String, Integer> e : map.entrySet()) result.add(e.getValue() + " " + e.getKey());
        return result;
    }

    public static void main(String[] args) {
        Problem15_SubdomainVisitCount sol = new Problem15_SubdomainVisitCount();
        System.out.println(sol.subdomainVisits(new String[]{"9001 discuss.leetcode.com"}));
    }
}
