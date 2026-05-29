import java.util.*;

public class Problem41_APIPaginationStrategy {
    static int[] data = new int[100];
    static { for (int i = 0; i < 100; i++) data[i] = i * 2; }
    
    // API returns page of results
    static int[] fetchPage(int offset, int limit) {
        int end = Math.min(offset + limit, data.length);
        if (offset >= data.length) return new int[0];
        return Arrays.copyOfRange(data, offset, end);
    }
    
    // Binary search across paginated API for target value
    static int paginatedSearch(int target, int pageSize) {
        int lo = 0, hi = data.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int[] page = fetchPage(mid, 1);
            if (page.length == 0) { hi = mid - 1; continue; }
            if (page[0] == target) return mid;
            else if (page[0] < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Search 42: index=" + paginatedSearch(42, 10)); // 21
    }
}
