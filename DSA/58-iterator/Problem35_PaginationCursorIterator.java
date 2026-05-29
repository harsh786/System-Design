import java.util.*;

public class Problem35_PaginationCursorIterator implements Iterator<List<String>> {
    List<String> data;
    int cursor = 0, pageSize;

    public Problem35_PaginationCursorIterator(List<String> data, int pageSize) {
        this.data = data; this.pageSize = pageSize;
    }

    public boolean hasNext() { return cursor < data.size(); }

    public List<String> next() {
        List<String> page = data.subList(cursor, Math.min(cursor + pageSize, data.size()));
        cursor += pageSize;
        return page;
    }

    public String getCursor() { return String.valueOf(cursor); }

    public static void main(String[] args) {
        List<String> data = Arrays.asList("a","b","c","d","e","f","g","h");
        Problem35_PaginationCursorIterator it = new Problem35_PaginationCursorIterator(data, 3);
        while (it.hasNext()) System.out.println("Page (cursor=" + it.getCursor() + "): " + it.next());
    }
}
