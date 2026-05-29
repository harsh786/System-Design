import java.util.*;

public class Problem36_DatabaseResultSetIterator implements Iterator<Map<String, Object>> {
    // Simulate database ResultSet iteration
    String[] columns;
    List<Object[]> rows;
    int idx = 0;

    public Problem36_DatabaseResultSetIterator(String[] columns, List<Object[]> rows) {
        this.columns = columns; this.rows = rows;
    }

    public boolean hasNext() { return idx < rows.size(); }

    public Map<String, Object> next() {
        Map<String, Object> row = new LinkedHashMap<>();
        Object[] data = rows.get(idx++);
        for (int i = 0; i < columns.length; i++) row.put(columns[i], data[i]);
        return row;
    }

    public static void main(String[] args) {
        String[] cols = {"id", "name", "age"};
        List<Object[]> rows = Arrays.asList(
            new Object[]{1, "Alice", 30}, new Object[]{2, "Bob", 25}, new Object[]{3, "Charlie", 35});
        Problem36_DatabaseResultSetIterator it = new Problem36_DatabaseResultSetIterator(cols, rows);
        while (it.hasNext()) System.out.println(it.next());
    }
}
