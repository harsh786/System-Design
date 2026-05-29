import java.util.*;

public class Problem30_PathCrossing {
    public static boolean isPathCrossing(String path) {
        Set<String> visited = new HashSet<>();
        int x = 0, y = 0;
        visited.add("0,0");
        for (char c : path.toCharArray()) {
            if (c == 'N') y++; else if (c == 'S') y--; else if (c == 'E') x++; else x--;
            if (!visited.add(x + "," + y)) return true;
        }
        return false;
    }
    public static void main(String[] args) {
        System.out.println(isPathCrossing("NES")); // false
        System.out.println(isPathCrossing("NESWW")); // true
    }
}
