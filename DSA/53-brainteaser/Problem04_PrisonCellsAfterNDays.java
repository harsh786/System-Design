import java.util.*;

public class Problem04_PrisonCellsAfterNDays {
    static int[] prisonAfterNDays(int[] cells, int n) {
        Map<String, Integer> seen = new HashMap<>();
        boolean hasCycle = false;
        int day = 0;
        while (day < n) {
            int[] next = new int[8];
            for (int i = 1; i < 7; i++) next[i] = cells[i-1] == cells[i+1] ? 1 : 0;
            String key = Arrays.toString(next);
            if (seen.containsKey(key)) {
                int cycle = day - seen.get(key);
                int remaining = (n - day) % cycle;
                for (int r = 0; r < remaining; r++) {
                    int[] tmp = new int[8];
                    for (int i = 1; i < 7; i++) tmp[i] = next[i-1] == next[i+1] ? 1 : 0;
                    next = tmp;
                }
                return next;
            }
            seen.put(key, day);
            cells = next;
            day++;
        }
        return cells;
    }
    
    public static void main(String[] args) {
        int[] cells = {0,1,0,1,1,0,0,1};
        System.out.println(Arrays.toString(prisonAfterNDays(cells, 7)));
    }
}
