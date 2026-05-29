import java.util.*;

public class Problem42_CursorBasedSearch {
    static String[] items = {"apple","banana","cherry","date","elderberry","fig","grape"};
    
    // Cursor-based pagination: returns items after cursor
    static String[] fetchAfter(String cursor, int limit) {
        int start = 0;
        if (cursor != null) {
            for (int i = 0; i < items.length; i++) if (items[i].equals(cursor)) { start = i + 1; break; }
        }
        int end = Math.min(start + limit, items.length);
        return Arrays.copyOfRange(items, start, end);
    }
    
    static String findItem(String target) {
        String cursor = null;
        while (true) {
            String[] page = fetchAfter(cursor, 2);
            if (page.length == 0) return null;
            for (String s : page) if (s.equals(target)) return s;
            cursor = page[page.length - 1];
        }
    }
    
    public static void main(String[] args) {
        System.out.println("Found: " + findItem("date"));
        System.out.println("Found: " + findItem("zz"));
    }
}
