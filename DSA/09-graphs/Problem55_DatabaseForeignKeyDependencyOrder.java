import java.util.*;

/**
 * Problem 55: Database Foreign Key Dependency Order
 * 
 * Production Relevance:
 * - Database migrations must create/drop tables in FK dependency order
 * - Bulk data loading: parent tables before children (or disable FK checks)
 * - ORM cascade operations follow FK graph
 * - Schema visualization tools render FK relationships as DAG
 * 
 * Architect Considerations:
 * - Self-referencing FKs (e.g., employee.manager_id -> employee.id) = cycle
 * - Nullable FKs allow partial ordering flexibility
 * - Parallel migration: independent branches can run concurrently
 */
public class Problem55_DatabaseForeignKeyDependencyOrder {

    static class Table {
        String name;
        List<ForeignKey> foreignKeys = new ArrayList<>();

        Table(String name) { this.name = name; }
    }

    static class ForeignKey {
        String column;
        String referencesTable;
        boolean nullable;

        ForeignKey(String column, String refTable, boolean nullable) {
            this.column = column; this.referencesTable = refTable; this.nullable = nullable;
        }
    }

    static class SchemaGraph {
        Map<String, Table> tables = new LinkedHashMap<>();

        void addTable(String name) { tables.put(name, new Table(name)); }

        void addFK(String table, String column, String refTable, boolean nullable) {
            tables.get(table).foreignKeys.add(new ForeignKey(column, refTable, nullable));
        }

        // Topological sort for CREATE order (parents first)
        List<String> getCreateOrder() {
            Map<String, Integer> inDegree = new HashMap<>();
            tables.keySet().forEach(t -> inDegree.put(t, 0));

            for (Table t : tables.values()) {
                for (ForeignKey fk : t.foreignKeys) {
                    if (!fk.nullable) { // Only mandatory FKs create hard dependency
                        inDegree.merge(t.name, 1, Integer::sum);
                    }
                }
            }

            // Build adjacency: referenced -> dependent
            Map<String, List<String>> adj = new HashMap<>();
            for (Table t : tables.values()) {
                for (ForeignKey fk : t.foreignKeys) {
                    if (!fk.nullable) {
                        adj.computeIfAbsent(fk.referencesTable, k -> new ArrayList<>()).add(t.name);
                    }
                }
            }

            Queue<String> queue = new LinkedList<>();
            inDegree.forEach((t, d) -> { if (d == 0) queue.offer(t); });

            List<String> order = new ArrayList<>();
            while (!queue.isEmpty()) {
                String t = queue.poll();
                order.add(t);
                for (String dep : adj.getOrDefault(t, List.of())) {
                    if (inDegree.merge(dep, -1, Integer::sum) == 0) queue.offer(dep);
                }
            }

            if (order.size() < tables.size()) {
                System.out.println("WARNING: Circular FK dependency detected!");
            }
            return order;
        }

        // DROP order = reverse of CREATE
        List<String> getDropOrder() {
            List<String> create = getCreateOrder();
            List<String> drop = new ArrayList<>(create);
            Collections.reverse(drop);
            return drop;
        }

        // Find parallel groups (tables at same level can be created concurrently)
        List<List<String>> getParallelGroups() {
            Map<String, Integer> level = new HashMap<>();
            tables.keySet().forEach(t -> level.put(t, 0));

            // BFS level assignment
            for (Table t : tables.values()) {
                for (ForeignKey fk : t.foreignKeys) {
                    if (!fk.nullable) {
                        level.merge(t.name, 1, (a, b) -> Math.max(a, level.getOrDefault(fk.referencesTable, 0) + 1));
                    }
                }
            }

            // Multiple passes to propagate levels
            for (int i = 0; i < tables.size(); i++) {
                for (Table t : tables.values()) {
                    for (ForeignKey fk : t.foreignKeys) {
                        if (!fk.nullable) {
                            int parentLevel = level.get(fk.referencesTable);
                            level.merge(t.name, parentLevel + 1, Math::max);
                        }
                    }
                }
            }

            TreeMap<Integer, List<String>> groups = new TreeMap<>();
            level.forEach((t, l) -> groups.computeIfAbsent(l, k -> new ArrayList<>()).add(t));
            return new ArrayList<>(groups.values());
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Database Foreign Key Dependency Order ===\n");

        SchemaGraph schema = new SchemaGraph();
        schema.addTable("users");
        schema.addTable("roles");
        schema.addTable("user_roles");
        schema.addTable("orders");
        schema.addTable("order_items");
        schema.addTable("products");
        schema.addTable("categories");

        schema.addFK("user_roles", "user_id", "users", false);
        schema.addFK("user_roles", "role_id", "roles", false);
        schema.addFK("orders", "user_id", "users", false);
        schema.addFK("order_items", "order_id", "orders", false);
        schema.addFK("order_items", "product_id", "products", false);
        schema.addFK("products", "category_id", "categories", false);

        System.out.println("CREATE order: " + schema.getCreateOrder());
        System.out.println("DROP order:   " + schema.getDropOrder());
        System.out.println("\nParallel groups (can run concurrently within group):");
        List<List<String>> groups = schema.getParallelGroups();
        for (int i = 0; i < groups.size(); i++) {
            System.out.printf("  Level %d: %s%n", i, groups.get(i));
        }
    }
}
