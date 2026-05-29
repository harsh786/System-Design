import java.util.*;

public class Problem04_FindDuplicateFileInSystem {
    public List<List<String>> findDuplicate(String[] paths) {
        Map<String, List<String>> map = new HashMap<>();
        for (String path : paths) {
            String[] parts = path.split(" ");
            String dir = parts[0];
            for (int i = 1; i < parts.length; i++) {
                int paren = parts[i].indexOf('(');
                String file = parts[i].substring(0, paren);
                String content = parts[i].substring(paren + 1, parts[i].length() - 1);
                map.computeIfAbsent(content, k -> new ArrayList<>()).add(dir + "/" + file);
            }
        }
        List<List<String>> result = new ArrayList<>();
        for (List<String> group : map.values()) if (group.size() > 1) result.add(group);
        return result;
    }

    public static void main(String[] args) {
        Problem04_FindDuplicateFileInSystem sol = new Problem04_FindDuplicateFileInSystem();
        System.out.println(sol.findDuplicate(new String[]{"root/a 1.txt(abcd) 2.txt(efgh)","root/c 3.txt(abcd)"}));
    }
}
