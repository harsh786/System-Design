import java.util.*;

public class Problem32_BacktrackingCombinationIterator implements Iterator<List<Integer>> {
    int n, k;
    int[] state;
    boolean hasMore;

    public Problem32_BacktrackingCombinationIterator(int n, int k) {
        this.n = n; this.k = k;
        state = new int[k];
        for (int i = 0; i < k; i++) state[i] = i + 1;
        hasMore = k <= n;
    }

    public boolean hasNext() { return hasMore; }

    public List<Integer> next() {
        List<Integer> result = new ArrayList<>();
        for (int s : state) result.add(s);
        // Generate next combination
        int i = k - 1;
        while (i >= 0 && state[i] == n - k + 1 + i) i--;
        if (i < 0) hasMore = false;
        else { state[i]++; for (int j = i+1; j < k; j++) state[j] = state[j-1]+1; }
        return result;
    }

    public static void main(String[] args) {
        Problem32_BacktrackingCombinationIterator it = new Problem32_BacktrackingCombinationIterator(5, 3);
        while (it.hasNext()) System.out.println(it.next());
    }
}
