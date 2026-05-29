import java.util.*;

public class Problem11_PagedAPIIterator implements Iterator<String> {
    int currentPage = 0, idx = 0;
    List<String> currentBatch = new ArrayList<>();
    int pageSize;
    List<String> allData; // simulated backend

    public Problem11_PagedAPIIterator(List<String> data, int pageSize) {
        this.allData = data; this.pageSize = pageSize; fetchPage();
    }

    void fetchPage() {
        currentBatch.clear(); idx = 0;
        int start = currentPage * pageSize;
        for (int i = start; i < Math.min(start + pageSize, allData.size()); i++)
            currentBatch.add(allData.get(i));
        currentPage++;
    }

    public boolean hasNext() {
        if (idx < currentBatch.size()) return true;
        if (currentPage * pageSize >= allData.size() + pageSize) return false;
        fetchPage();
        return !currentBatch.isEmpty();
    }

    public String next() { return currentBatch.get(idx++); }

    public static void main(String[] args) {
        List<String> data = Arrays.asList("a","b","c","d","e","f","g");
        Problem11_PagedAPIIterator it = new Problem11_PagedAPIIterator(data, 3);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
