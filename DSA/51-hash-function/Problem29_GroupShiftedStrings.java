import java.util.*;

public class Problem29_GroupShiftedStrings {
    public List<List<String>> groupStrings(String[] strings) {
        Map<String, List<String>> map = new HashMap<>();
        for (String s : strings) {
            StringBuilder key = new StringBuilder();
            for (int i = 1; i < s.length(); i++) {
                int diff = (s.charAt(i) - s.charAt(i-1) + 26) % 26;
                key.append(diff).append(",");
            }
            map.computeIfAbsent(key.toString(), k -> new ArrayList<>()).add(s);
        }
        return new ArrayList<>(map.values());
    }

    public static void main(String[] args) {
        Problem29_GroupShiftedStrings sol = new Problem29_GroupShiftedStrings();
        System.out.println(sol.groupStrings(new String[]{"abc","bcd","acef","xyz","az","ba","a","z"}));
    }
}
