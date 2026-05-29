import java.util.*;

public class Problem33_PermutationIterator implements Iterator<List<Integer>> {
    int[] perm;
    boolean hasMore;

    public Problem33_PermutationIterator(int n) {
        perm = new int[n];
        for (int i = 0; i < n; i++) perm[i] = i + 1;
        hasMore = true;
    }

    public boolean hasNext() { return hasMore; }

    public List<Integer> next() {
        List<Integer> result = new ArrayList<>();
        for (int p : perm) result.add(p);
        // Next permutation
        int i = perm.length - 2;
        while (i >= 0 && perm[i] >= perm[i+1]) i--;
        if (i < 0) { hasMore = false; return result; }
        int j = perm.length - 1;
        while (perm[j] <= perm[i]) j--;
        int t = perm[i]; perm[i] = perm[j]; perm[j] = t;
        for (int l = i+1, r = perm.length-1; l < r; l++, r--) { t=perm[l];perm[l]=perm[r];perm[r]=t; }
        return result;
    }

    public static void main(String[] args) {
        Problem33_PermutationIterator it = new Problem33_PermutationIterator(3);
        while (it.hasNext()) System.out.println(it.next());
    }
}
