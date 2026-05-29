import java.util.*;

public class Problem39_DesignFileSystemPathHashing {
    private Map<String, Integer> paths = new HashMap<>();

    public Problem39_DesignFileSystemPathHashing() { paths.put("", -1); }

    public boolean createPath(String path, int value) {
        if (paths.containsKey(path)) return false;
        String parent = path.substring(0, path.lastIndexOf('/'));
        if (!paths.containsKey(parent)) return false;
        paths.put(path, value);
        return true;
    }

    public int get(String path) { return paths.getOrDefault(path, -1); }

    public static void main(String[] args) {
        Problem39_DesignFileSystemPathHashing fs = new Problem39_DesignFileSystemPathHashing();
        System.out.println(fs.createPath("/a", 1)); // true
        System.out.println(fs.createPath("/a/b", 2)); // true
        System.out.println(fs.get("/a/b")); // 2
        System.out.println(fs.createPath("/c/d", 3)); // false
    }
}
