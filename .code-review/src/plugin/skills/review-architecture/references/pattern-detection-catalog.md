# Design pattern detection

## Pattern Detection (Grep)

| Group | Pattern | Detection Keywords | File Types |
|-------|---------|-------------------|------------|
| Creational | Singleton | `_instance\|__new__\|@singleton\|SingletonMeta\|getInstance` | *.py, *.ts, *.js, *.java, *.cs |
| Creational | Factory | `Factory\|create_.*instance\|FactoryMethod\|AbstractFactory\|factory_method` | *.py, *.ts, *.js, *.java, *.cs |
| Creational | Builder | `Builder\|\.build()\|with_.*return.*self\|\.set_.*\.set_` | *.py, *.ts, *.js, *.java, *.cs |
| Structural | Adapter | `Adapter\|adapt(\|Protocol.*class.*ABC\|implements.*Port` | *.py, *.ts, *.js, *.java, *.cs |
| Structural | Pipeline | `Pipeline\|Stage\|PipelineStep\|add_stage\|compose_stages\|pipe_chain` | *.py, *.ts, *.js, *.go |
| Behavioral | Strategy | `Strategy\|StrategyPattern\|set_strategy\|execute_strategy\|HandlerRegistry` | *.py, *.ts, *.js, *.java, *.cs |
| Behavioral | Template Method | `@abstractmethod.*def\|class.*ABC.*:.*def\|template_method\|TemplateMethod` | *.py, *.ts, *.js, *.java |
| Behavioral | Registry | `_registry\|register(\|get_handler\|_handlers\[\|HandlerRegistry` | *.py, *.ts, *.js |
| Behavioral | Orchestrator | `Orchestrator\|orchestrate\|WorkflowEngine\|step.*execute` | *.py, *.ts, *.js |
| Architecture | Service Layer | `class.*Service.*:\|ServiceLayer\|ApplicationService\|@Service` | *.py, *.ts, *.js, *.java, *.cs |
| Architecture | Dependency Injection | `Depends(\|@inject\|container\|Provider\|bind\|Injector` | *.py, *.ts, *.js, *.java, *.cs |
| Architecture | Repository | `Repository\|findBy\|findOne\|save\|delete\|@Repository` | *.ts, *.js, *.py, *.java |
| Architecture | CQRS | `Command\|Query\|ReadModel\|WriteModel\|CommandHandler` | *.ts, *.js, *.cs |
| Architecture | Event Sourcing | `EventStore\|Aggregate\|AggregateRoot\|DomainEvent` | *.ts, *.js, *.cs |
| Infrastructure | Job Processing | `Queue\|Worker\|Job\|Bull\|BullMQ\|Celery\|Sidekiq` | *.ts, *.js, *.py, *.rb |
| Infrastructure | Event-Driven | `EventEmitter\|publish\|subscribe\|emit\|on(\s*['"]` | *.ts, *.js, *.py |
| Infrastructure | Caching | `Cache\|Redis\|Memcached\|TTL\|invalidate\|@Cacheable` | *.ts, *.js, *.py, *.java |
| Infrastructure | Resilience | `CircuitBreaker\|Retry\|Timeout\|Fallback\|Bulkhead` | *.ts, *.js, *.py |
| Infrastructure | Message Queue | `RabbitMQ\|Kafka\|SQS\|AMQP\|MessageBroker` | *.ts, *.js, *.py |
| Infrastructure | HTTP Client | `httpx.AsyncClient\|aiohttp.ClientSession\|HttpClient\|RestClient\|ApiClient` | *.py, *.ts, *.js, *.java |
| Infrastructure | API Gateway | `Gateway\|Proxy\|RateLimit\|ApiGateway` | *.ts, *.js, *.py |
| Infrastructure | Rate Limiting | `RateLimit\|rate_limit\|slowapi\|throttle\|@rate_limit\|Throttle` | *.py, *.ts, *.js, *.java |
| Communication | Saga | `Saga\|SagaStep\|Compensate\|compensat` | *.ts, *.js, *.py |
| Communication | Client Notification | `notify\|callback_url\|webhook\|SSE\|EventSource\|WebSocket.*send` | *.py, *.ts, *.js |
| Data | Parameter Object | `@dataclass.*frozen\|NamedTuple\|TypedDict\|ValueObject\|@value_object` | *.py, *.ts, *.js, *.java, *.cs |
| Data | Fail-Fast Validation | `ValidationError\|@validator\|@validate\|pydantic.BaseModel\|field_validator` | *.py, *.ts, *.js |
| Architecture | Flat Orchestration | `Orchestrator\|Coordinator\|Workflow\|UseCase\|CommandHandler` | *.py, *.ts, *.js, *.java, *.cs |

## Discovery Heuristics

### Structural Heuristics

| Heuristic | Detection | Inferred Pattern |
|-----------|-----------|-----------------|
| Class naming conventions | `Grep("class\s+\w*(Factory\|Builder\|Strategy\|Adapter\|Observer\|Decorator\|Proxy\|Mediator\|Command\|Visitor\|State\|Chain\|Facade)")` | GoF pattern matching class name suffix |
| Abstract hierarchy | Find ABC/abstract classes with 2+ concrete implementations in same directory | Template Method or Strategy |
| Fluent interface | `return self\|return this` chains in non-test code (3+ methods in same class) | Builder |
| Registration dict | `_registry\|_handlers\|_map\s*[=:]\s*\{` with `register(` method in same file | Registry |
| Middleware chain | `app.use(\|add_middleware(\|@app.middleware` | Chain of Responsibility |
| Event listeners | `@on_event\|addEventListener\|@receiver\|signal\|on_.*_event` | Observer |
| Decorator wrappers | `@wraps\|functools.wraps\|__wrapped__` in non-framework code | Decorator pattern |
| State machine | `state\|transition\|current_state\|StateMachine\|FSM` | State pattern |
| Pub/Sub | `subscriber\|publisher\|topic\|channel\|broadcast` outside message queue context | Observer / Mediator |
