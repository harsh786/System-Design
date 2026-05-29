import java.util.*;

/**
 * Problem 63: Schema Migration Dependency Graph
 * 
 * Production Relevance:
 * - Database migrations (Flyway, Liquibase, Alembic) must execute in dependency order
 * - Multi-team environments: parallel migration branches that must merge correctly
 * - Zero-downtime migrations require expand-contract pattern with dependency tracking
 * - Rollback planning: which migrations can safely revert without breaking dependents
 * 
 * Architect Considerations:
 * - Linear versioning (Flyway) vs DAG versioning (Alembic heads)
 * - Idempotent migrations for retry safety
 * - Schema compatibility: forward/backward compatible during rolling deploys
 */
public class Problem63_SchemaMigrationDependencyGraph {

    static class Migration {
        String id;
        String description;
        List<String> dependsOn;
        String upSQL;
        String downSQL;
        boolean applied;

        Migration(String id, String desc, String up, String down, String... deps) {
            this.id = id; this.description = desc; this.upSQL = up; this.downSQL = down;
            this.dependsOn = Arrays.asList(deps);
        }
    }

    static class MigrationEngine {
        Map<String, Migration> migrations = new LinkedHashMap<>();
        Set<String> applied = new LinkedHashSet<>();

        void register(Migration m) { migrations.put(m.id, m); }

        // Compute execution order respecting dependencies
        List<String> planForward() {
            Map<String, Integer> inDeg = new HashMap<>();
            Map<String, List<String>> dependents = new HashMap<>();
            migrations.keySet().forEach(m -> { inDeg.put(m, 0); dependents.put(m, new ArrayList<>()); });

            for (Migration m : migrations.values()) {
                for (String dep : m.dependsOn) {
                    dependents.computeIfAbsent(dep, k -> new ArrayList<>()).add(m.id);
                    inDeg.merge(m.id, 1, Integer::sum);
                }
            }

            Queue<String> ready = new PriorityQueue<>(); // deterministic ordering
            inDeg.forEach((m, d) -> { if (d == 0 && !applied.contains(m)) ready.offer(m); });

            List<String> plan = new ArrayList<>();
            while (!ready.isEmpty()) {
                String m = ready.poll();
                if (applied.contains(m)) continue;
                plan.add(m);
                for (String dep : dependents.getOrDefault(m, List.of())) {
                    if (inDeg.merge(dep, -1, Integer::sum) == 0 && !applied.contains(dep)) {
                        ready.offer(dep);
                    }
                }
            }
            return plan;
        }

        // Plan rollback: reverse order, only unapply those without dependents still applied
        List<String> planRollback(String targetMigration) {
            List<String> toRollback = new ArrayList<>();
            // Find all migrations that depend (transitively) on target
            Set<String> needsRollback = new LinkedHashSet<>();
            findDependents(targetMigration, needsRollback);
            needsRollback.add(targetMigration);

            // Sort in reverse dependency order
            List<String> forward = planForward();
            // Use applied + forward order to determine reverse
            List<String> allApplied = new ArrayList<>(applied);
            for (int i = allApplied.size() - 1; i >= 0; i--) {
                if (needsRollback.contains(allApplied.get(i))) {
                    toRollback.add(allApplied.get(i));
                }
            }
            return toRollback;
        }

        private void findDependents(String migrationId, Set<String> result) {
            for (Migration m : migrations.values()) {
                if (m.dependsOn.contains(migrationId) && applied.contains(m.id)) {
                    if (result.add(m.id)) findDependents(m.id, result);
                }
            }
        }

        void apply(String migrationId) {
            Migration m = migrations.get(migrationId);
            System.out.printf("  APPLY %s: %s [%s]%n", m.id, m.description, m.upSQL);
            applied.add(migrationId);
            m.applied = true;
        }

        void rollback(String migrationId) {
            Migration m = migrations.get(migrationId);
            System.out.printf("  ROLLBACK %s: %s [%s]%n", m.id, m.description, m.downSQL);
            applied.remove(migrationId);
            m.applied = false;
        }

        // Detect merge conflicts (multiple heads)
        List<String> findHeads() {
            Set<String> hasDependent = new HashSet<>();
            for (Migration m : migrations.values()) hasDependent.addAll(m.dependsOn);
            List<String> heads = new ArrayList<>();
            for (String id : migrations.keySet()) {
                if (!hasDependent.contains(id)) heads.add(id);
            }
            return heads;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Schema Migration Dependency Graph ===\n");

        MigrationEngine engine = new MigrationEngine();
        engine.register(new Migration("001", "Create users table", "CREATE TABLE users...", "DROP TABLE users"));
        engine.register(new Migration("002", "Create orders table", "CREATE TABLE orders...", "DROP TABLE orders", "001"));
        engine.register(new Migration("003", "Add email to users", "ALTER TABLE users ADD email...", "ALTER TABLE users DROP email", "001"));
        engine.register(new Migration("004", "Create order_items", "CREATE TABLE order_items...", "DROP TABLE order_items", "002"));
        engine.register(new Migration("005", "Add index on orders", "CREATE INDEX...", "DROP INDEX...", "002", "003"));

        System.out.println("Migration heads (leaf nodes): " + engine.findHeads());
        System.out.println("\nForward plan:");
        List<String> plan = engine.planForward();
        for (String m : plan) engine.apply(m);

        System.out.println("\nRollback plan for migration 002:");
        List<String> rollback = engine.planRollback("002");
        System.out.println("Must rollback: " + rollback);
        for (String m : rollback) engine.rollback(m);
    }
}
